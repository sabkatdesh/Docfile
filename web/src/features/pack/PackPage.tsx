import { ExternalLink } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { asProblem, problemMessage } from "../../api/problem";
import { usePack } from "../../api/queries";
import { Button, Card, EmptyState, ErrorState, Skeleton } from "../../components/ui/primitives";
import { Tabs } from "../../components/ui/Tabs";
import { packLabel } from "../../lib/verdict";
import { ComparisonCard } from "./ComparisonCard";
import { EvidenceText } from "./EvidenceText";
import { FieldList } from "./FieldList";
import { marksOf } from "./marks";
import { RuleChecklist } from "./RuleChecklist";
import { Timeline } from "./Timeline";
import { VerdictCard } from "./VerdictCard";

function PackSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-2" aria-busy="true">
      <Skeleton className="h-96" />
      <div className="space-y-4">
        <Skeleton className="h-40" />
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}

export function PackPage() {
  const { packId = "" } = useParams();
  const query = usePack(packId);
  const [active, setActive] = useState<{ id: string | null; pulse: number }>({
    id: null,
    pulse: 0,
  });
  const detail = query.data;
  const marks = useMemo(() => (detail ? marksOf(detail) : []), [detail]);

  const select = (id: string) => setActive((a) => ({ id, pulse: a.pulse + 1 }));

  if (query.isPending) return <PackSkeleton />;

  if (query.isError) {
    const problem = asProblem(query.error);
    if (problem.code === "no_result") {
      return (
        <EmptyState
          title={`${packLabel(packId)} has not been checked yet`}
          action={
            <Link to="/">
              <Button variant="primary">Go to the dashboard to run it</Button>
            </Link>
          }
        >
          There is nothing to show until the packs have been run.
        </EmptyState>
      );
    }
    return (
      <ErrorState
        title="This pack could not be loaded"
        message={problemMessage(problem)}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const d = query.data;
  const issueCount = d.fields.filter((f) => f.status !== "OK").length;
  const failing = d.rules.filter((r) => r.status !== "PASS").length;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to="/" className="text-sm text-accent underline-offset-2 hover:underline">
            Back to all packs
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {packLabel(d.pack_id)}
          </h1>
          <p className="text-muted">{d.source_file}</p>
        </div>
        <a href={d.pdf_url} target="_blank" rel="noreferrer">
          <Button icon={<ExternalLink size={16} aria-hidden="true" />}>Open original PDF</Button>
        </a>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card aria-labelledby="doc-heading" className="lg:sticky lg:top-4">
          <h2 id="doc-heading" className="mb-1 text-base font-semibold">
            What the document says
          </h2>
          <p className="mb-3 text-sm text-muted">
            Highlighted words are the exact quotes the checks rely on.
          </p>
          <div className="max-h-[70vh] overflow-auto rounded-lg border border-line bg-surface-2 p-4">
            <EvidenceText text={d.text} marks={marks} activeId={active.id} pulse={active.pulse} />
          </div>
        </Card>

        <div className="space-y-6">
          <VerdictCard detail={d} />
          <Card aria-labelledby="detail-heading">
            <h2 id="detail-heading" className="sr-only">
              Details
            </h2>
            <Tabs
              label="Pack details"
              tabs={[
                {
                  id: "fields",
                  label: "Fields",
                  badge:
                    issueCount > 0 ? (
                      <span className="rounded-full bg-review-bg px-2 text-xs text-review-fg">
                        {issueCount}
                        <span className="sr-only"> need attention</span>
                      </span>
                    ) : null,
                  content: <FieldList fields={d.fields} activeId={active.id} onSelect={select} />,
                },
                {
                  id: "comparison",
                  label: "Comparison",
                  content: <ComparisonCard comparison={d.comparison} onSelect={select} />,
                },
                {
                  id: "rules",
                  label: "Rules",
                  badge:
                    failing > 0 ? (
                      <span className="rounded-full bg-reject-bg px-2 text-xs text-reject-fg">
                        {failing}
                        <span className="sr-only"> not passed</span>
                      </span>
                    ) : null,
                  content: <RuleChecklist rules={d.rules} onSelect={select} />,
                },
                { id: "timeline", label: "Timeline", content: <Timeline detail={d} /> },
              ]}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}
