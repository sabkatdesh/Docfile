import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createBrowserRouter, type RouteObject, RouterProvider } from "react-router";
import { Shell } from "./components/Shell";
import { ToastProvider } from "./components/ui/Toast";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { EvaluationPage } from "./features/evaluation/EvaluationPage";
import { PackPage } from "./features/pack/PackPage";
import { ReviewPage } from "./features/review/ReviewPage";
import { ThemeProvider } from "./lib/theme";
import { type EventSourceFactory, RunProvider } from "./state/RunProvider";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "packs/:packId", element: <PackPage /> },
      { path: "review", element: <ReviewPage /> },
      { path: "evaluation", element: <EvaluationPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-muted">Use the menu above to go to the dashboard.</p>
    </div>
  );
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: 1, staleTime: 0, refetchOnWindowFocus: false } },
  });
}

export function Providers({
  children,
  eventSourceFactory,
  queryClient,
}: {
  children: React.ReactNode;
  eventSourceFactory?: EventSourceFactory;
  queryClient?: QueryClient;
}) {
  const [client] = useState(() => queryClient ?? makeQueryClient());
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <ToastProvider>
          <RunProvider eventSourceFactory={eventSourceFactory}>{children}</RunProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export function App() {
  const [router] = useState(() => createBrowserRouter(routes));
  return (
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  );
}
