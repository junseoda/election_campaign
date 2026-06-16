import { NextResponse } from "next/server";
import { getEvaluationDashboard } from "../../_lib/campaignData";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(getEvaluationDashboard());
}
