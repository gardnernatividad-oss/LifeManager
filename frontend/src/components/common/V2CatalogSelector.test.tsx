import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/v2CatalogApi";
import { CategorySelector, TaskCatalogSelector } from "./V2CatalogSelector";

vi.mock("../../api/v2CatalogApi", () => ({ listV2CatalogSelector: vi.fn() }));

function renderSelector(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("V2 catalog selectors", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses active-only server semantics by default", async () => {
    vi.mocked(api.listV2CatalogSelector).mockResolvedValue([{ id: "active", name: "Casa", is_active: true, category_id: null, category_name: null }]);
    renderSelector(<CategorySelector workspaceId="workspace-a" value="" onChange={vi.fn()} />);
    expect(await screen.findByRole("option", { name: "Casa" })).toBeInTheDocument();
    expect(api.listV2CatalogSelector).toHaveBeenCalledWith("workspace-a", "categories", undefined, undefined);
  });

  it("requests and labels the current inactive option explicitly", async () => {
    vi.mocked(api.listV2CatalogSelector).mockResolvedValue([{ id: "inactive", name: "Anterior", is_active: false, category_id: "category", category_name: "Casa" }]);
    renderSelector(<TaskCatalogSelector workspaceId="workspace-a" currentId="inactive" value="inactive" onChange={vi.fn()} />);
    expect(await screen.findByRole("option", { name: "Anterior (Inactiva)" })).toBeInTheDocument();
    expect(api.listV2CatalogSelector).toHaveBeenCalledWith("workspace-a", "tasks", "inactive", undefined);
  });

  it("isolates cache and requests when the Workspace changes", async () => {
    vi.mocked(api.listV2CatalogSelector).mockResolvedValue([]);
    const view = renderSelector(<CategorySelector workspaceId="workspace-a" value="" onChange={vi.fn()} />);
    await screen.findByText("No hay opciones activas disponibles.");
    view.rerender(<QueryClientProvider client={new QueryClient()}><CategorySelector workspaceId="workspace-b" value="" onChange={vi.fn()} /></QueryClientProvider>);
    await screen.findByText("No hay opciones activas disponibles.");
    expect(api.listV2CatalogSelector).toHaveBeenCalledWith("workspace-b", "categories", undefined, undefined);
  });
});
