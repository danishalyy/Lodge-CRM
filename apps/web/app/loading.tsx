import { Skeleton } from "@/components/ui/skeleton";
export default function Loading() {
  return (
    <main className="content" aria-label="Loading page" role="status">
      <Skeleton className="h-10 w-48 mb-6" />
      <div className="grid gap-6 sm:grid-cols-2">
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
      <span className="sr-only">Loading your workspace…</span>
    </main>
  );
}
