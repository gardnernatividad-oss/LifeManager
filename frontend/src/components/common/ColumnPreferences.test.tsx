import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect } from "vitest";
import { useColumnPreferences, ColumnPreferences, type ColumnOption } from "./ColumnPreferences";

const columns: ColumnOption[] = [{ key: "date", label: "Fecha" }, { key: "responsible", label: "Responsable", defaultVisible: false }];
function Fixture() { const state = useColumnPreferences("user-1", "tasks", columns); return <ColumnPreferences columns={columns} visible={state.visible} onChange={state.setVisible} />; }

it("persists column preferences per user and view", async () => {
  localStorage.clear(); const user = userEvent.setup(); const first = render(<Fixture />);
  await user.click(screen.getByText("Columnas"));
  expect(screen.getByLabelText("Mostrar columna Fecha")).toBeChecked();
  expect(screen.getByLabelText("Mostrar columna Responsable")).not.toBeChecked();
  await user.click(screen.getByLabelText("Mostrar columna Responsable"));
  expect(JSON.parse(localStorage.getItem("lifemanager.columns.user-1.tasks") ?? "[]")).toContain("responsible");
  first.unmount(); render(<Fixture />); await user.click(screen.getByText("Columnas"));
  expect(screen.getByLabelText("Mostrar columna Responsable")).toBeChecked();
});
