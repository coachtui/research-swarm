import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// Routes that require authentication
const isProtectedRoute = createRouteMatcher([
  "/analyze(.*)",
  "/dashboard(.*)",
  "/results(.*)",
]);

export default clerkMiddleware(async (auth, request) => {
  if (isProtectedRoute(request)) {
    const { userId } = await auth();
    if (!userId) {
      // Redirect unauthenticated users to sign-up (not sign-in).
      // Preserve the destination so Clerk redirects back after account creation.
      const signUpUrl = new URL("/sign-up", request.url);
      signUpUrl.searchParams.set(
        "redirect_url",
        request.nextUrl.pathname + request.nextUrl.search
      );
      signUpUrl.searchParams.set("intent", "free");
      return NextResponse.redirect(signUpUrl);
    }
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
};
