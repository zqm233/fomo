import { NextRequest, NextResponse } from "next/server";

const ALLOWED_HOSTS = new Set(["wechatrss.waytomaster.com"]);

/** Render 后端代拉公众号 RSS（绕过云主机 IP 被 CF 403）；仅允许 waytomaster 域名 */
export async function POST(req: NextRequest) {
  let body: { url?: string; headers?: Record<string, string> };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "invalid json" }, { status: 400 });
  }

  const raw = body.url?.trim();
  if (!raw) {
    return NextResponse.json({ detail: "url required" }, { status: 400 });
  }

  let target: URL;
  try {
    target = new URL(raw);
  } catch {
    return NextResponse.json({ detail: "invalid url" }, { status: 400 });
  }

  if (target.protocol !== "https:" || !ALLOWED_HOSTS.has(target.hostname.toLowerCase())) {
    return NextResponse.json({ detail: "host not allowed" }, { status: 403 });
  }

  const forwardHeaders: Record<string, string> = {
    "User-Agent":
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    Accept: "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US,en;q=0.8",
    Referer: `${target.origin}/`,
    Origin: target.origin,
    ...body.headers,
  };

  const upstream = await fetch(raw, {
    headers: forwardHeaders,
    redirect: "follow",
    cache: "no-store",
  });

  const buf = await upstream.arrayBuffer();
  const contentType = upstream.headers.get("content-type") ?? "application/xml";

  return new NextResponse(buf, {
    status: upstream.status,
    headers: { "Content-Type": contentType },
  });
}
