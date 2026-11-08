import { aiCopy as copy } from "@/lib/strings/ai";
import { knowledgeCopy } from "@/lib/strings/knowledge";
import { readableLabel } from "@/lib/strings/content";
import { formatDate, formatDateTime } from "@/lib/formatting";
export default function MessageSources({ sources }: { sources?: any[] }) {
  return (
    <details className="aiSources">
      <summary>
        <span>{copy.sources}</span>
        <span className="aiSourceCount" aria-hidden="true">
          {sources?.length || 0}
        </span>
      </summary>
      {sources?.length ? (
        <ul>
          {sources.map((s: any, i: number) => (
            <li key={i}>
              {s.label || copy.live} · {formatDateTime(s.retrieved_at)}
              {s.partial && <span> · {copy.partial}</span>}
              {s.kind === "group" && (
                <>
                  <p>
                    {copy.groupScope}: {s.group_name}
                  </p>
                  {s.excluded_count > 0 && (
                    <p>{copy.excludedLodges(s.excluded_count)}</p>
                  )}
                  <ul>
                    {s.references?.map((ref: any) => (
                      <li key={ref.lodge_id}>
                        {ref.lodge_name} · {ref.timezone}
                        {ref.period
                          ? ` · ${formatDate(ref.period.start_date)} – ${formatDate(ref.period.end_date)} (UTC)`
                          : ref.current_date
                            ? ` · ${formatDate(ref.current_date)}`
                            : ""}
                      </li>
                    ))}
                  </ul>
                  {s.contributors && (
                    <details>
                      <summary>{copy.metricCoverage}</summary>
                      <ul>
                        {Object.entries(s.contributors).map(([metric, ids]) => (
                          <li key={metric}>
                            {readableLabel(metric)}:{" "}
                            {(ids as string[])
                              .map(
                                (id) =>
                                  s.references?.find(
                                    (ref: any) => ref.lodge_id === id,
                                  )?.lodge_name || id,
                              )
                              .join(", ")}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </>
              )}
              {s.kind === "document" && (
                <ul>
                  {s.references?.map((ref: any) => (
                    <li key={ref.id}>
                      {knowledgeCopy.source}: {ref.title} · {ref.locator} ·{" "}
                      {knowledgeCopy.passage} {ref.id}
                    </li>
                  ))}
                </ul>
              )}
              {s.kind === "memory" && (
                <>
                  <p>
                    {copy.memory} · {copy.period}:{" "}
                    {formatDate(s.period?.start_date)} –{" "}
                    {formatDate(s.period?.end_date)}
                  </p>
                  <ul>
                    {s.references?.map((ref: any) => (
                      <li key={ref.id}>
                        {copy.event} {ref.id} ·{" "}
                        {formatDateTime(ref.recorded_at)}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p>{copy.noSources}</p>
      )}
    </details>
  );
}
