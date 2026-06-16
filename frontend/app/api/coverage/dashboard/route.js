import { NextResponse } from "next/server";
import { getCoverageDashboard } from "../../_lib/campaignData";

export const dynamic = "force-dynamic";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const limit = Number(searchParams.get("limit")) || 12;
  return NextResponse.json(getCoverageDashboard(limit));
}
