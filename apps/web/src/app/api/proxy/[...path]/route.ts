import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return forwardRequest(req, params.path);
}

export async function POST(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return forwardRequest(req, params.path);
}

export async function PUT(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return forwardRequest(req, params.path);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return forwardRequest(req, params.path);
}

async function forwardRequest(req: NextRequest, pathParts: string[]) {
  const path = "/" + pathParts.join("/");
  const url = new URL(path + req.nextUrl.search, BACKEND_URL);

  const headers = new Headers(req.headers);
  headers.set("host", url.host);

  // If internal service key configured, pass it
  if (process.env.INTERNAL_API_KEY) {
    headers.set("Authorization", `Bearer ${process.env.INTERNAL_API_KEY}`);
  }

  const body = req.method !== "GET" && req.method !== "HEAD" ? await req.blob() : undefined;

  try {
    const res = await fetch(url.toString(), {
      method: req.method,
      headers,
      body,
      // @ts-ignore
      duplex: "half",
    });

    return new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: res.headers,
    });
  } catch (err: any) {
    return NextResponse.json(
      {
        error: {
          code: "PROXY_ERROR",
          message: "Failed to reach backend API",
          details: { error: err.message },
        },
      },
      { status: 502 }
    );
  }
}

