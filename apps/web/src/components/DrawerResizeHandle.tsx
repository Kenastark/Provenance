import { useCallback, useEffect, useRef } from "react";

/**
 * The station detail drawer's left-edge drag handle.
 *
 * `lg`-only: below that breakpoint the drawer is stacked full-width and a resize
 * handle has nothing to do, so callers hide it with a responsive class rather than
 * this component unmounting itself - unmounting mid-breakpoint-change would drop
 * focus if a keyboard user were on it.
 *
 * Follows the ARIA "window splitter" pattern: `role="separator"` with
 * `aria-orientation="vertical"`, a numeric value triple so a screen reader can
 * announce the current width, and left/right arrow keys as the keyboard
 * equivalent of the drag. Double-click resets to the token default, mirroring the
 * conventional behaviour of a splitter handle.
 */

const KEY_STEP = 16;

export interface DrawerResizeHandleProps {
  width: number;
  min: number;
  max: number;
  onResize: (width: number) => void;
  onReset: () => void;
  className?: string;
}

export function DrawerResizeHandle({
  width,
  min,
  max,
  onResize,
  onReset,
  className,
}: DrawerResizeHandleProps) {
  // The handle sits on the drawer's *left* edge: dragging it left (toward the map)
  // widens the drawer, so the delta is start-minus-current, not the other way round.
  const drag = useRef<{ startX: number; startWidth: number } | null>(null);
  const onResizeRef = useRef(onResize);
  onResizeRef.current = onResize;

  const handlePointerMove = useCallback((event: PointerEvent) => {
    if (!drag.current) return;
    onResizeRef.current(drag.current.startWidth + (drag.current.startX - event.clientX));
  }, []);

  const stopDrag = useCallback(() => {
    drag.current = null;
    window.removeEventListener("pointermove", handlePointerMove);
    window.removeEventListener("pointerup", stopDrag);
  }, [handlePointerMove]);

  useEffect(() => stopDrag, [stopDrag]);

  const handlePointerDown = useCallback(
    (event: React.PointerEvent) => {
      if (event.button !== 0) return;
      drag.current = { startX: event.clientX, startWidth: width };
      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", stopDrag);
      event.preventDefault();
    },
    [width, handlePointerMove, stopDrag],
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === "ArrowLeft") {
        onResize(width + KEY_STEP);
        event.preventDefault();
      } else if (event.key === "ArrowRight") {
        onResize(width - KEY_STEP);
        event.preventDefault();
      } else if (event.key === "Home") {
        onResize(min);
        event.preventDefault();
      } else if (event.key === "End") {
        onResize(max);
        event.preventDefault();
      }
    },
    [width, min, max, onResize],
  );

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize station detail panel"
      aria-valuenow={Math.round(width)}
      aria-valuemin={Math.round(min)}
      aria-valuemax={Math.round(max)}
      tabIndex={0}
      data-testid="drawer-resize-handle"
      className={[
        "w-2 shrink-0 cursor-col-resize touch-none select-none",
        "hover:bg-interactive focus-visible:bg-interactive",
        className ?? "",
      ].join(" ")}
      onPointerDown={handlePointerDown}
      onKeyDown={handleKeyDown}
      onDoubleClick={onReset}
    />
  );
}
