import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DrawerResizeHandle } from "../components/DrawerResizeHandle";

function renderHandle(overrides: Partial<React.ComponentProps<typeof DrawerResizeHandle>> = {}) {
  const onResize = vi.fn();
  const onReset = vi.fn();
  render(
    <DrawerResizeHandle
      width={480}
      min={360}
      max={800}
      onResize={onResize}
      onReset={onReset}
      {...overrides}
    />,
  );
  return { onResize, onReset };
}

describe("DrawerResizeHandle", () => {
  it("exposes itself as a keyboard-operable vertical separator with an accessible name", () => {
    renderHandle();
    const handle = screen.getByTestId("drawer-resize-handle");
    expect(handle).toHaveAttribute("role", "separator");
    expect(handle).toHaveAttribute("aria-orientation", "vertical");
    expect(handle).toHaveAttribute("aria-valuenow", "480");
    expect(handle).toHaveAttribute("aria-valuemin", "360");
    expect(handle).toHaveAttribute("aria-valuemax", "800");
    expect(handle).toHaveAccessibleName(/resize/i);
    expect(handle).toHaveAttribute("tabIndex", "0");
  });

  it("ArrowLeft widens the drawer and ArrowRight narrows it, in fixed steps", async () => {
    const user = userEvent.setup();
    const { onResize } = renderHandle({ width: 480 });
    const handle = screen.getByTestId("drawer-resize-handle");
    handle.focus();

    await user.keyboard("{ArrowLeft}");
    expect(onResize).toHaveBeenLastCalledWith(496);

    await user.keyboard("{ArrowRight}");
    expect(onResize).toHaveBeenLastCalledWith(464);
  });

  it("Home and End jump to the min and max", async () => {
    const user = userEvent.setup();
    const { onResize } = renderHandle({ width: 480, min: 360, max: 800 });
    const handle = screen.getByTestId("drawer-resize-handle");
    handle.focus();

    await user.keyboard("{Home}");
    expect(onResize).toHaveBeenLastCalledWith(360);

    await user.keyboard("{End}");
    expect(onResize).toHaveBeenLastCalledWith(800);
  });

  it("double-click resets to the token default", async () => {
    const user = userEvent.setup();
    const { onReset } = renderHandle();
    await user.dblClick(screen.getByTestId("drawer-resize-handle"));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
