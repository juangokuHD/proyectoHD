import { Router, type IRouter } from "express";
import healthRouter from "./health";
import parkingRouter from "./parking";

const router: IRouter = Router();

router.use(healthRouter);
router.use(parkingRouter);

export default router;
