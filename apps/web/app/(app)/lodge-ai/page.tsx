import LodgeAIPage from "@/components/LodgeAIPage";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ scope?: string; report?: string }>;
}) {
  const params = await searchParams;
  const scope = params.scope === "group" ? "group" : "lodge";
  const report =
    typeof params.report === "string" && /^[0-9a-f-]{36}$/i.test(params.report)
      ? params.report
      : undefined;
  return (
    <LodgeAIPage
      key={`${scope}:${report || ""}`}
      scopeType={scope}
      initialReportId={report}
    />
  );
}
