import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type PropsWithChildren } from "react";
import { RouterProvider } from "react-router-dom";

import { appRouter } from "../router";
import { AuthProvider } from "./AuthContext";

function QueryProvider({ children }: PropsWithChildren) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 30_000
          }
        }
      })
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

export function AppProviders() {
  return (
    <QueryProvider>
      <AuthProvider>
        <RouterProvider router={appRouter} />
      </AuthProvider>
    </QueryProvider>
  );
}
