import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { ApiProblem } from "./problem";
import { asProblem } from "./problem";
import type { PackListItem, ReviewRequest } from "./types";

export const keys = {
  health: ["health"] as const,
  packs: ["packs"] as const,
  pack: (id: string) => ["pack", id] as const,
  review: ["review"] as const,
  eval: ["eval"] as const,
};

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.health });
export const usePacks = () => useQuery({ queryKey: keys.packs, queryFn: api.packs });
export const useReview = () => useQuery({ queryKey: keys.review, queryFn: api.review });
export const useEval = () => useQuery({ queryKey: keys.eval, queryFn: api.eval });

export const usePack = (id: string) =>
  useQuery({ queryKey: keys.pack(id), queryFn: () => api.pack(id) });

/** Every screen that can change after a review decision or a run. */
export function useInvalidateAll(): () => Promise<void> {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: keys.packs }),
      client.invalidateQueries({ queryKey: keys.review }),
      client.invalidateQueries({ queryKey: keys.eval }),
      client.invalidateQueries({ queryKey: keys.health }),
      client.invalidateQueries({ queryKey: ["pack"] }),
    ]);
  };
}

export function useResolveReview() {
  const invalidate = useInvalidateAll();
  return useMutation<PackListItem, ApiProblem, { packId: string; body: ReviewRequest }>({
    mutationFn: async ({ packId, body }) => {
      try {
        return await api.resolve(packId, body);
      } catch (error) {
        throw asProblem(error);
      }
    },
    onSuccess: () => invalidate(),
  });
}
