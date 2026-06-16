import { NextResponse } from "next/server";
import { getRecommendationResponse } from "../../_lib/campaignData";

export const dynamic = "force-dynamic";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  return NextResponse.json(await getRecommendationResponse({
    query_id: searchParams.get("query_id"),
    limit: Number(searchParams.get("limit")) || 10,
  }));
}
