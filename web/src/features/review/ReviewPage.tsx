import { Link } from "react-router";
import { asProblem, problemMessage } from "../../api/problem";
import { useReview } from "../../api/queries";
import {
  Button,
  EmptyState,
  ErrorState,
  PageTitle,
  Skeleton,
} from "../../components/ui/primitives";
import { ReviewCard } from "./ReviewCard";

export function ReviewPage() {
  const query = useReview();

  return (
    <div>
      <PageTitle title="Review queue" />
      {query.isPending ? (
        <div className="space-y-4" aria-busy="true">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      ) : query.isError ? (
        <ErrorState
          title="The review queue could not be loaded"
          message={problemMessage(asProblem(query.error))}
          onRetry={() => void query.refetch()}
        />
      ) : query.data.length === 0 ? (
        <EmptyState
          title="Nothing is waiting for a person"
          action={
            <Link to="/">
              <Button>Back to the dashboard</Button>
            </Link>
          }
        >
          Packs the checker could not settle on its own show up here.
        </EmptyState>
      ) : (
        <>
          <p className="mb-4 text-muted">
            {query.data.length} {query.data.length === 1 ? "pack needs" : "packs need"} your
            decision. Approving or rejecting is final and is saved with your reason.
          </p>
          <div className="space-y-6">
            {query.data.map((item) => (
              <ReviewCard key={item.pack_id} item={item} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
