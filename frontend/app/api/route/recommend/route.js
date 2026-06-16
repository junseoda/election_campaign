import { NextResponse } from "next/server";
import { getRouteResponse } from "../../_lib/campaignData";

export const dynamic = "force-dynamic";

export async function POST(request) {
  const payload = await request.json().catch(() => ({}));
  return NextResponse.json(await getRouteResponse(payload));
}
