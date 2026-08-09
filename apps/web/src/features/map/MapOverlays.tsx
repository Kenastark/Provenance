import { StateGlyph } from "../../components/StateGlyph";
import { formatMeasurement, formatTimestamp } from "../../lib/format";
import { trustStateLabel, type TrustState } from "../../lib/trust";
import { compassPoint, MAP_LAYERS, type LayerId, type StationMarker, type WindVector } from "./stationMarkers";
import type { WindEdge } from "./windEdges";

/**
 * Everything drawn *over* the basemap: markers, wind, legend, layer switches.
 *
 * All of it is React DOM rather than GL, so every marker is a real button with an
 * accessible name and a tab stop, and the whole overlay renders under jsdom for the
 * component tests. Position comes from the engine's projection; when the engine has
 * not initialised the markers are still in the DOM (at the origin, hidden from
 * sight but not from assistive technology), which is what keeps a WebGL-less
 * environment from silently losing the station list.
 */

export interface StationMarkerLayerProps {
  markers: readonly StationMarker[];
  project: (lon: number, lat: number) => { x: number; y: number } | null;
  selectedStationId: string | null;
  onSelect: (stationId: string) => void;
}

export function StationMarkerLayer({
  markers,
  project,
  selectedStationId,
  onSelect,
}: StationMarkerLayerProps) {
  return (
    <ul
      className="pointer-events-none absolute inset-0 m-0 list-none overflow-hidden p-0"
      data-testid="station-marker-layer"
      aria-label="Monitoring stations"
    >
      {markers.map((marker) => {
        const point = project(marker.lon, marker.lat);
        const selected = marker.stationId === selectedStationId;
        const name = [
          marker.stationId,
          marker.name,
          trustStateLabel(marker.state),
          marker.hasActiveEvent ? "active event" : null,
        ]
          .filter(Boolean)
          .join(", ");

        return (
          <li
            key={marker.stationId}
            className="pointer-events-auto absolute"
            style={{
              transform: `translate(${(point?.x ?? 0) - 12}px, ${(point?.y ?? 0) - 12}px)`,
              visibility: point ? "visible" : "hidden",
            }}
          >
            <button
              type="button"
              onClick={() => onSelect(marker.stationId)}
              aria-label={name}
              aria-pressed={selected}
              data-testid="station-marker"
              data-station={marker.stationId}
              data-state={marker.state}
              data-has-event={marker.hasActiveEvent ? "true" : "false"}
              title={name}
              className={[
                "relative flex h-5 w-5 items-center justify-center rounded-full border bg-bg-raised",
                `prov-state-${marker.state}`,
                selected ? "border-interactive" : "border-border-strong",
              ].join(" ")}
            >
              <StateGlyph state={marker.state} size={12} decorative />
              {marker.hasActiveEvent && (
                <span
                  aria-hidden="true"
                  data-testid="event-glyph"
                  // The event glyph is a second, independent channel: a station can
                  // be amber for a slow drift or amber with an active event, and
                  // those are different jobs for the operator.
                  className="absolute -right-1 -top-1 flex h-3 w-3 items-center justify-center rounded-full border border-border-strong bg-surface text-micro leading-none prov-state-fault"
                >
                  !
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export interface WindEdgeLayerProps {
  edges: readonly WindEdge[];
  project: (lon: number, lat: number) => { x: number; y: number } | null;
}

/**
 * The wind-conditioned edges, drawn under the markers.
 *
 * Each edge is a line from a station to a downwind neighbour, its width and opacity
 * scaled by the edge weight so the strongest downwind links read first, ending in an
 * arrowhead that points the way the plume would travel. Pure SVG over the projected
 * positions; when the GL engine has not initialised (no WebGL, e.g. under jsdom) the
 * projection returns null and the layer renders nothing rather than at the origin.
 */
export function WindEdgeLayer({ edges, project }: WindEdgeLayerProps) {
  const maxWeight = edges.reduce((m, e) => Math.max(m, e.weight), 0) || 1;
  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      data-testid="wind-edge-layer"
      aria-hidden="true"
    >
      <defs>
        <marker
          id="wind-edge-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--prov-interactive)" />
        </marker>
      </defs>
      {edges.map((edge) => {
        const a = project(edge.srcLon, edge.srcLat);
        const b = project(edge.dstLon, edge.dstLat);
        if (!a || !b) return null;
        const strength = edge.weight / maxWeight;
        return (
          <line
            key={`${edge.srcId}-${edge.dstId}`}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="var(--prov-interactive)"
            strokeWidth={0.75 + strength * 2.5}
            strokeOpacity={0.2 + strength * 0.6}
            markerEnd="url(#wind-edge-arrow)"
            data-testid="wind-edge"
            data-src={edge.srcId}
            data-dst={edge.dstId}
          />
        );
      })}
    </svg>
  );
}

export function WindOverlay({ wind }: { wind: WindVector | null }) {
  if (!wind) {
    return (
      <div
        className="prov-panel absolute right-7 top-3 p-3 text-caption text-text-tertiary shadow-overlay"
        data-map-overlay=""
      data-testid="wind-overlay-empty"
      >
        <p className="text-text-secondary">Wind</p>
        <p className="mt-1">No wind readings in this window.</p>
      </div>
    );
  }

  const point = compassPoint(wind.directionDegrees);
  const summary = `Wind from ${point}, ${Math.round(wind.directionDegrees)} degrees, ${formatMeasurement(wind.speed, wind.speedUnit)}`;

  return (
    <div
      // right-7 clears MapLibre's own zoom control, which sits in the same corner.
      className="prov-panel absolute right-7 top-3 flex items-center gap-3 p-3 shadow-overlay"
      data-map-overlay=""
      data-testid="wind-overlay"
      data-direction={Math.round(wind.directionDegrees)}
    >
      <svg width={32} height={32} viewBox="0 0 32 32" role="img" aria-label={summary}>
        <title>{summary}</title>
        {/* The barb points the way the air is going: bearings are reported as the
            direction the wind comes *from*, so the arrow is rotated 180 from it. */}
        <g transform={`rotate(${wind.directionDegrees + 180} 16 16)`}>
          <line x1="16" y1="26" x2="16" y2="6" stroke="var(--prov-interactive)" strokeWidth="2" />
          <path d="M16 4 L11 12 L16 9.5 L21 12 Z" fill="var(--prov-interactive)" />
        </g>
      </svg>
      <div className="text-caption">
        <p className="prov-numeric font-mono text-body text-text">
          {point} {formatMeasurement(wind.speed, wind.speedUnit)}
        </p>
        <p className="text-text-tertiary">
          {Math.round(wind.directionDegrees)}° · {wind.stationCount} station
          {wind.stationCount === 1 ? "" : "s"}
        </p>
        <p className="text-text-tertiary">{formatTimestamp(wind.observedAt)}</p>
      </div>
    </div>
  );
}

export function MapLegend({ counts }: { counts: Record<TrustState, number> }) {
  const states: TrustState[] = ["verified", "degraded", "fault", "unknown"];
  return (
    <div
      className="prov-panel absolute bottom-3 right-3 p-3 text-caption shadow-overlay"
      data-map-overlay=""
      data-testid="map-legend"
    >
      <p className="mb-2 text-text-secondary">Trust state</p>
      <ul className="m-0 list-none space-y-1 p-0">
        {states.map((state) => (
          <li key={state} className={`flex items-center gap-2 prov-state-${state}`}>
            <StateGlyph state={state} size={12} decorative />
            <span className="text-text">{trustStateLabel(state)}</span>
            <span className="prov-numeric ml-auto pl-3 font-mono text-text-tertiary">
              {counts[state]}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export interface LayerTogglesProps {
  enabled: Record<LayerId, boolean>;
  onToggle: (id: LayerId, next: boolean) => void;
}

export function LayerToggles({ enabled, onToggle }: LayerTogglesProps) {
  return (
    <fieldset
      className="prov-panel absolute left-3 top-3 p-3 text-caption shadow-overlay"
      data-map-overlay=""
      data-testid="layer-toggles"
    >
      <legend className="px-1 text-text-secondary">Layers</legend>
      <ul className="m-0 list-none space-y-2 p-0">
        {MAP_LAYERS.map((layer) => (
          <li key={layer.id}>
            <label
              className={[
                "flex items-center gap-2",
                layer.available ? "text-text" : "text-text-tertiary",
              ].join(" ")}
              title={layer.available ? undefined : layer.unavailableReason}
            >
              <input
                type="checkbox"
                checked={layer.available ? enabled[layer.id] : false}
                disabled={!layer.available}
                onChange={(event) => onToggle(layer.id, event.target.checked)}
                data-testid={`layer-toggle-${layer.id}`}
              />
              <span>{layer.label}</span>
              {!layer.available && (
                <span className="text-micro text-text-tertiary">(phase 4)</span>
              )}
            </label>
            {!layer.available && <p className="sr-only">{layer.unavailableReason}</p>}
          </li>
        ))}
      </ul>
    </fieldset>
  );
}
