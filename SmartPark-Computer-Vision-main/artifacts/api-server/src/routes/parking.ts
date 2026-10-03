import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { Router, type IRouter } from "express";
import { logger } from "../lib/logger";
import {
  AnalyzeParkingImageBody,
  AnalyzeParkingImageResponse,
  DeleteParkingCameraParams,
  DeleteParkingCameraResponse,
  ListParkingCamerasResponse,
  SaveParkingCameraBody,
  SaveParkingCameraResponse,
} from "@workspace/api-zod";

type ParkingCamera = {
  id: string;
  name: string;
  referenceWidth: number;
  referenceHeight: number;
  spaces: { id: string; polygon: { x: number; y: number }[] }[];
};

type WorkerResponse = {
  requestId: string;
  ok: boolean;
  error?: string;
  result?: unknown;
};

const router: IRouter = Router();
const dataDirectory = path.resolve(process.cwd(), "../smartpark/data");
const configPath = path.join(dataDirectory, "parking_spaces.json");
const visionDirectory = path.resolve(process.cwd(), "../smartpark");
let workerProcess: ChildProcessWithoutNullStreams | null = null;
let nextRequestId = 0;
let workerOutput = "";
const pendingRequests = new Map<
  string,
  { resolve: (value: unknown) => void; reject: (error: Error) => void }
>();

async function readCameras(): Promise<ParkingCamera[]> {
  await mkdir(dataDirectory, { recursive: true });
  try {
    const contents = await readFile(configPath, "utf8");
    const parsed: unknown = JSON.parse(contents);
    return ListParkingCamerasResponse.parse(parsed);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      await writeFile(configPath, "[]\n", "utf8");
      return [];
    }
    throw error;
  }
}

async function writeCameras(cameras: ParkingCamera[]): Promise<void> {
  await mkdir(dataDirectory, { recursive: true });
  const temporaryPath = `${configPath}.${randomUUID()}.tmp`;
  await writeFile(temporaryPath, `${JSON.stringify(cameras, null, 2)}\n`, "utf8");
  await rename(temporaryPath, configPath);
}

function rejectPending(error: Error): void {
  for (const pending of pendingRequests.values()) {
    pending.reject(error);
  }
  pendingRequests.clear();
}

function getWorker(): ChildProcessWithoutNullStreams {
  if (workerProcess && workerProcess.exitCode === null && !workerProcess.killed) {
    return workerProcess;
  }

  workerOutput = "";
  const child = spawn(
    process.env.PYTHON_EXECUTABLE ?? "python",
    ["-m", "vision.worker"],
    { cwd: visionDirectory, stdio: ["pipe", "pipe", "pipe"] },
  );
  workerProcess = child;
  child.stderr.on("data", (chunk: Buffer) => {
    const message = chunk.toString().trim();
    if (message) {
      logger.debug({ output: message }, "Local vision worker output");
    }
  });
  child.stdout.on("data", (chunk: Buffer) => {
    workerOutput += chunk.toString("utf8");
    let newlineIndex = workerOutput.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = workerOutput.slice(0, newlineIndex);
      workerOutput = workerOutput.slice(newlineIndex + 1);
      newlineIndex = workerOutput.indexOf("\n");
      if (!line.trim()) {
        continue;
      }
      try {
        const response = JSON.parse(line) as WorkerResponse;
        const pending = pendingRequests.get(response.requestId);
        if (!pending) {
          continue;
        }
        pendingRequests.delete(response.requestId);
        if (response.ok) {
          pending.resolve(response.result);
        } else {
          pending.reject(new Error(response.error ?? "Local vision processing failed."));
        }
      } catch (error) {
        rejectPending(
          error instanceof Error ? error : new Error("Invalid vision worker response."),
        );
      }
    }
  });
  child.on("error", (error) => {
    rejectPending(new Error(`Could not start the local vision worker: ${error.message}`));
    if (workerProcess === child) {
      workerProcess = null;
    }
  });
  child.on("exit", (code, signal) => {
    if (workerProcess === child) {
      workerProcess = null;
    }
    rejectPending(
      new Error(
        `The local vision worker stopped (${signal ?? `exit ${code ?? "unknown"}`}).`,
      ),
    );
  });
  return child;
}

function askVisionWorker(payload: {
  imageBase64: string;
  camera: ParkingCamera;
  confidence: number;
}): Promise<unknown> {
  const child = getWorker();
  const requestId = String(++nextRequestId);
  return new Promise((resolve, reject) => {
    pendingRequests.set(requestId, { resolve, reject });
    child.stdin.write(`${JSON.stringify({ ...payload, requestId })}\n`, (error) => {
      if (error) {
        pendingRequests.delete(requestId);
        reject(error);
      }
    });
  });
}

router.get("/parking/cameras", async (req, res): Promise<void> => {
  try {
    res.json(ListParkingCamerasResponse.parse(await readCameras()));
  } catch (error) {
    req.log.error({ err: error }, "Could not read parking camera configurations");
    res.status(500).json({ error: "Could not read saved camera configurations." });
  }
});

router.post("/parking/cameras", async (req, res): Promise<void> => {
  const parsed = SaveParkingCameraBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }
  const camera = parsed.data as ParkingCamera;
  if (
    camera.name.trim().length === 0 ||
    camera.referenceWidth <= 0 ||
    camera.referenceHeight <= 0
  ) {
    res.status(400).json({
      error: "Camera name and positive reference image dimensions are required.",
    });
    return;
  }

  try {
    const cameras = await readCameras();
    const updated = cameras.filter((entry) => entry.id !== camera.id);
    updated.push(camera);
    await writeCameras(updated);
    res.json(SaveParkingCameraResponse.parse(camera));
  } catch (error) {
    req.log.error({ err: error }, "Could not save parking camera configuration");
    res.status(500).json({ error: "Could not save this camera configuration." });
  }
});

router.delete("/parking/cameras/:cameraId", async (req, res): Promise<void> => {
  const params = DeleteParkingCameraParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }
  try {
    const cameras = await readCameras();
    const updated = cameras.filter((camera) => camera.id !== params.data.cameraId);
    await writeCameras(updated);
    res.json(DeleteParkingCameraResponse.parse({ deleted: updated.length !== cameras.length }));
  } catch (error) {
    req.log.error({ err: error }, "Could not delete parking camera configuration");
    res.status(500).json({ error: "Could not delete this camera configuration." });
  }
});

router.post("/parking/analyze", async (req, res): Promise<void> => {
  const parsed = AnalyzeParkingImageBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }
  const { cameraId, imageBase64, confidence } = parsed.data;
  if (imageBase64.length > 36_000_000) {
    res.status(413).json({ error: "Please upload an image smaller than 25 MB." });
    return;
  }

  try {
    const cameras = await readCameras();
    const camera = cameras.find((entry) => entry.id === cameraId);
    if (!camera) {
      res.status(404).json({ error: "This camera configuration was not found." });
      return;
    }
    if (camera.spaces.length === 0) {
      res.status(400).json({
        error: "This camera has no parking spaces yet. Configure at least one first.",
      });
      return;
    }
    const result = await askVisionWorker({ imageBase64, camera, confidence });
    res.json(AnalyzeParkingImageResponse.parse(result));
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Local vision processing failed.";
    req.log.error({ err: error }, "Parking image analysis failed");
    const status = message.includes("Ultralytics is not installed") ? 503 : 500;
    res.status(status).json({ error: message });
  }
});

export default router;