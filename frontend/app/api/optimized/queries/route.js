import { NextResponse } from "next/server";
import { getOptimizedQueries } from "../../_lib/campaignData";

export const dynamic = "force-dynamic";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const limit = Number(searchParams.get("limit")) || 100;
  return NextResponse.json(getOptimizedQueries(limit));
}
