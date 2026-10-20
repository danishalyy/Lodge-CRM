import {NextRequest, NextResponse} from 'next/server';

const SESSION_COOKIE_NAME = process.env.SESSION_COOKIE_NAME || 'lodge_session';
const PUBLIC_PATHS = new Set(['/', '/login', '/activate', '/forgot-password', '/reset-password', '/icon.svg']);

export function middleware(request: NextRequest) {
  const {pathname} = request.nextUrl;
  if (PUBLIC_PATHS.has(pathname) || pathname.startsWith('/_next') || pathname === '/favicon.ico') {
    return NextResponse.next();
  }
  if (!request.cookies.get(SESSION_COOKIE_NAME)?.value) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {matcher: ['/((?!api).*)']};
