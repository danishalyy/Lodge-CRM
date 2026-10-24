import LodgeAIPage from "@/components/LodgeAIPage";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ scope?: string }>;
}) {
  const scope = (await searchParams).scope === "group" ? "group" : "lodge";
  return <LodgeAIPage key={scope} scopeType={scope} />;
}
