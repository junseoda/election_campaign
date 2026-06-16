import { NextResponse } from "next/server";
import { getRouteOptions } from "../../_lib/campaignData";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({ ok: true, source: "local-data", ...getRouteOptions() });
}
