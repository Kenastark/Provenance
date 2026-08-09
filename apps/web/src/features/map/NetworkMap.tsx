import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useEvents, useQualitySummary, useReadings, useStations } from "../../api/queries";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useTheme } from "../../lib/theme";
import { useWindowState } from "../../lib/windowContext";
import { StationDetailPanel } from "../station/StationDetailPanel";
import { LayerToggles, MapLegend, StationMarkerLayer, WindOverlay } from "./MapOverlays";
import { useMapEngine } from "./useMapEngine";
import {
  buildStationMarkers,
  currentWind,
  MAP_LAYERS,
  summariseMarkers,
  WIND_DIRECTION_PARAMETER,
  type LayerId,
  type StationMarker,
} from "./stationMarkers";

/**
 * The primary screen: the network, coloured by trust.
 *
 * The selected station lives in the URL (`?station=STA-01`), so a link to a station
 * is a link an operator can paste into a ticket - and so the browser's back button
 * does what it looks like it does.
 */

const DEFAULT_LAYERS = Object.fromEntries(
  MAP_LAYERS.map((layer) => [layer.id, layer.defaultOn]),
) as Record<LayerId, boolean>;

export function NetworkMap() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedStationId = searchParams.get("station");

  const stations = useStations();
  const quality = useQualitySummary();
  const events = useEvents();

  const { markers, withoutCoordinates } = useMemo(
    () =>
      buildStationMarkers({
        stations: stations.data ?? [],
        quality: quality.data?.stations ?? [],
        events: events.data ?? [],
      }),
    [stations.data, quality.data, events.data],
  );

  const selectStation = useCallback(
    (stationId: string | null) => {
      setSearchParams((previous) => {
        const next = new URLSearchParams(previous);
        if (stationId) next.set("station", stationId);
        else next.delete("station");
        return next;
      });
    },
    [setSearchParams],
  );

  if (stations.isLoading || quality.isLoading) {
    return <LoadingState label="Loading the network" />;
  }
  if (stations.error) {
    return (
      <ErrorState error={stations.error} what="load the station list" onRetry={stations.refetch} />
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col lg:flex-row">
      <MapSurface
        markers={markers}
        withoutCoordinates={withoutCoordinates}
        hasStations={(stations.data?.length ?? 0) > 0}
        selectedStationId={selectedStationId}
        onSelect={selectStation}
      />

      <StationDetailPanel
        stationId={selectedStationId}
        station={stations.data?.find((s) => s.station_id === selectedStationId) ?? null}
        qualityRow={quality.data?.stations.find((s) => s.station_id === selectedStationId) ?? null}
        onClose={() => selectStation(null)}
      />
    </div>
  );
}

/**
 * The map surface itself.
 *
 * Split out so it only mounts once the data has arrived - which means the GL
 * container exists by the time the engine attaches to it. Initialising the map from
 * a mount effect on the parent silently produces a blank map, because on the
 * parent's first render the container is still behind the loading state.
 */
function MapSurface({
  markers,
  withoutCoordinates,
  hasStations,
  selectedStationId,
  onSelect,
}: {
  markers: readonly StationMarker[];
  withoutCoordinates: readonly string[];
  hasStations: boolean;
  selectedStationId: string | null;
  onSelect: (stationId: string) => void;
}) {
  const { resolved } = useWindowState();
  const { resolved: theme } = useTheme();
  const [layers, setLayers] = useState<Record<LayerId, boolean>>(DEFAULT_LAYERS);
  const { containerRef, project, basemapAvailable, isIdle } = useMapEngine(markers, theme);

  // Wind is a network-level readout, taken across the stations that carry a wind
  // sensor rather than from a nominated one. Stations without one contribute
  // nothing, and a network-wide absence reads as "no data", never as a calm.
  const windReadings = useReadings({
    stationId: markers[0]?.stationId,
    parameter: WIND_DIRECTION_PARAMETER,
    start: resolved.start,
    end: resolved.end,
    limit: 200,
    enabled: markers.length > 0,
  });
  const wind = useMemo(() => currentWind(windReadings.data ?? []), [windReadings.data]);
  const counts = useMemo(() => summariseMarkers(markers), [markers]);

  return (
    // overflow-hidden matters: the marker overlay is absolutely positioned and a
    // marker can sit outside the section's box mid-animation. Without clipping,
    // the browser treats the section as scrollable and any scroll-into-view shifts
    // the whole overlay, so a marker never settles under the pointer.
    <section
      className="relative min-w-0 flex-1 overflow-hidden"
      aria-label="Network map"
      // Exposed so the e2e can wait for the map to settle rather than sleep, and so
      // a visual snapshot is never taken mid-flight.
      data-map-state={isIdle ? "idle" : "moving"}
    >
      <div ref={containerRef} className="absolute inset-0 bg-bg" data-testid="map-canvas" />

      {markers.length === 0 ? (
        <div className="absolute inset-0 flex items-center justify-center p-4">
          <div className="prov-panel max-w-full">
            <EmptyState
              title="No stations to place on the map"
              description={
                hasStations
                  ? "The loaded stations carry no coordinates. Green Sentinel coordinates are parsed from the export's Location column; a corpus without it still audits, but cannot be mapped."
                  : "No stations have been loaded. Run `make demo` to load the demo corpus, or `prov db load --source data/raw` for a real drop."
              }
            />
          </div>
        </div>
      ) : (
        <>
          <StationMarkerLayer
            markers={markers}
            project={project}
            selectedStationId={selectedStationId}
            onSelect={onSelect}
          />
          <LayerToggles
            enabled={layers}
            onToggle={(id, next) => setLayers((previous) => ({ ...previous, [id]: next }))}
          />
          <WindOverlay wind={wind} />
          <MapLegend counts={counts} />
        </>
      )}

      {!basemapAvailable && markers.length > 0 && (
        <p
          className="prov-panel absolute left-1/2 top-3 -translate-x-1/2 p-2 text-caption text-text-tertiary"
          data-testid="basemap-unavailable"
        >
          Basemap unavailable in this browser — stations are placed by relative position only.
        </p>
      )}

      {withoutCoordinates.length > 0 && (
        <p
          className="prov-panel absolute bottom-3 left-3 p-2 text-caption text-text-tertiary"
          data-testid="stations-without-coordinates"
        >
          {withoutCoordinates.length} station{withoutCoordinates.length === 1 ? "" : "s"} not mapped
          (no coordinates): {withoutCoordinates.join(", ")}
        </p>
      )}
    </section>
  );
}
