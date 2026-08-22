import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  useAttentionOverlay,
  useBusStops,
  useEvents,
  useQualitySummary,
  useReadings,
  useStations,
  useTrafficCounters,
} from "../../api/queries";
import type { AttentionOverlay } from "../../api/client";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useTheme } from "../../lib/theme";
import { useWindowState } from "../../lib/windowContext";
import { StationDetailPanel } from "../station/StationDetailPanel";
import {
  AttentionEdgeLayer,
  LayerToggles,
  MapLegend,
  ReferenceMarkerLayer,
  StationMarkerLayer,
  WindEdgeLayer,
  WindOverlay,
} from "./MapOverlays";
import { useMapEngine } from "./useMapEngine";
import {
  buildBusStopMarkers,
  buildStationMarkers,
  buildTrafficCounterMarkers,
  currentWind,
  MAP_LAYERS,
  resolveMapLayers,
  summariseMarkers,
  WIND_DIRECTION_PARAMETER,
  WIND_LOOKBACK_HOURS,
  WIND_SPEED_PARAMETER,
  type BusStopMarker,
  type LayerDefinition,
  type LayerId,
  type MarkerProvenance,
  type StationMarker,
  type TrafficCounterMarker,
} from "./stationMarkers";
import { attentionEdgesFromOverlay, computeWindEdges } from "./windEdges";

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
  const busStops = useBusStops();
  const trafficCounters = useTrafficCounters();
  const attentionOverlay = useAttentionOverlay();

  const { markers, withoutCoordinates } = useMemo(
    () =>
      buildStationMarkers({
        stations: stations.data ?? [],
        quality: quality.data?.stations ?? [],
        events: events.data ?? [],
      }),
    [stations.data, quality.data, events.data],
  );

  const busStopMarkers = useMemo(() => buildBusStopMarkers(busStops.data?.stops ?? []), [busStops.data]);
  const trafficCounterMarkers = useMemo(
    () => buildTrafficCounterMarkers(trafficCounters.data?.counters ?? []),
    [trafficCounters.data],
  );
  const layerDefs = useMemo(
    () =>
      resolveMapLayers(MAP_LAYERS, {
        busStops: busStops.data,
        trafficCounters: trafficCounters.data,
        attentionOverlay: attentionOverlay.data,
      }),
    [busStops.data, trafficCounters.data, attentionOverlay.data],
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
        busStopMarkers={busStopMarkers}
        trafficCounterMarkers={trafficCounterMarkers}
        attentionOverlay={attentionOverlay.data}
        layerDefs={layerDefs}
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
  busStopMarkers,
  trafficCounterMarkers,
  attentionOverlay,
  layerDefs,
  selectedStationId,
  onSelect,
}: {
  markers: readonly StationMarker[];
  withoutCoordinates: readonly string[];
  hasStations: boolean;
  busStopMarkers: readonly BusStopMarker[];
  trafficCounterMarkers: readonly TrafficCounterMarker[];
  attentionOverlay: AttentionOverlay | undefined;
  layerDefs: readonly LayerDefinition[];
  selectedStationId: string | null;
  onSelect: (stationId: string) => void;
}) {
  const { anchor } = useWindowState();
  const { resolved: theme } = useTheme();
  const [layers, setLayers] = useState<Record<LayerId, boolean>>(DEFAULT_LAYERS);
  const { containerRef, project, basemapAvailable, tilesPresent, isIdle } = useMapEngine(
    markers,
    theme,
  );

  // Wind is a network-level readout, taken across every station that carries a wind
  // sensor rather than from one nominated station - stations without one simply
  // don't appear in either fetch, and a network-wide absence reads as "no data",
  // never as a calm. Direction and speed are two separate parameters, so they need
  // two requests (the API filters by exactly one `parameter` per call); currentWind
  // merges them back into one reading per station by matching timestamps.
  const windStart = useMemo(
    () => (anchor ? new Date(anchor.getTime() - WIND_LOOKBACK_HOURS * 3600_000).toISOString() : null),
    [anchor],
  );
  const windEnd = anchor ? anchor.toISOString() : null;
  const windDirectionReadings = useReadings({
    stationId: undefined,
    networkWide: true,
    parameter: WIND_DIRECTION_PARAMETER,
    start: windStart,
    end: windEnd,
    limit: 200,
    enabled: markers.length > 0,
  });
  const windSpeedReadings = useReadings({
    stationId: undefined,
    networkWide: true,
    parameter: WIND_SPEED_PARAMETER,
    start: windStart,
    end: windEnd,
    limit: 200,
    enabled: markers.length > 0,
  });
  const wind = useMemo(
    () => currentWind([...(windDirectionReadings.data ?? []), ...(windSpeedReadings.data ?? [])]),
    [windDirectionReadings.data, windSpeedReadings.data],
  );
  const counts = useMemo(() => summariseMarkers(markers), [markers]);
  const windEdges = useMemo(
    () => (layers.windEdges ? computeWindEdges(markers, wind) : []),
    [layers.windEdges, markers, wind],
  );
  const attentionAvailable = Boolean(attentionOverlay?.available);
  const attentionEdges = useMemo(
    () =>
      layers.attentionOverlay && attentionOverlay?.available
        ? attentionEdgesFromOverlay(attentionOverlay.relations ?? {}, markers)
        : [],
    [layers.attentionOverlay, attentionOverlay, markers],
  );

  const busStopDef = layerDefs.find((l) => l.id === "busStop");
  const trafficCounterDef = layerDefs.find((l) => l.id === "trafficCounter");
  const showBusStops = Boolean(busStopDef?.available) && layers.busStop;
  const showTrafficCounters = Boolean(trafficCounterDef?.available) && layers.trafficCounter;

  // What's actually on screen right now, derived rather than hardcoded (rule 1):
  // stations are always drawn once there are any, and the reference layers only
  // add to the set when their toggle is both available and switched on.
  const provenances = useMemo(() => {
    const set = new Set<MarkerProvenance>();
    if (markers.length > 0) set.add("measured");
    if (showBusStops) for (const m of busStopMarkers) set.add(m.provenance);
    if (showTrafficCounters) for (const m of trafficCounterMarkers) set.add(m.provenance);
    return set;
  }, [markers.length, showBusStops, busStopMarkers, showTrafficCounters, trafficCounterMarkers]);

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
          {layers.windEdges && <WindEdgeLayer edges={windEdges} project={project} />}
          {layers.attentionOverlay && attentionAvailable && (
            <AttentionEdgeLayer edges={attentionEdges} project={project} />
          )}
          {showBusStops && (
            <ReferenceMarkerLayer
              markers={busStopMarkers.map((m) => ({
                id: m.stopId,
                lat: m.lat,
                lon: m.lon,
                label: `Bus stop ${m.stopId}`,
                provenance: m.provenance,
              }))}
              project={project}
              kind="bus-stop"
              ariaLabel="Bus stops"
            />
          )}
          {showTrafficCounters && (
            <ReferenceMarkerLayer
              markers={trafficCounterMarkers.map((m) => ({
                id: m.counterId,
                lat: m.lat,
                lon: m.lon,
                label: m.name,
                provenance: m.provenance,
              }))}
              project={project}
              kind="traffic-counter"
              ariaLabel="Traffic counters"
            />
          )}
          <StationMarkerLayer
            markers={markers}
            project={project}
            selectedStationId={selectedStationId}
            onSelect={onSelect}
          />
          <LayerToggles
            layers={layerDefs}
            enabled={layers}
            onToggle={(id, next) => setLayers((previous) => ({ ...previous, [id]: next }))}
          />
          <WindOverlay wind={wind} />
          <MapLegend counts={counts} provenances={provenances} />
        </>
      )}

      {/* Two different degraded states, worded for two different fixes: MapLibre
          itself could not start (a browser/environment problem - no WebGL, a
          locked-down VM), versus MapLibre running fine on the token ground because
          `make basemap` was never run or was skipped (a `make basemap` problem). */}
      {!basemapAvailable && markers.length > 0 && (
        <p
          // Capped width: centred between the layer toggles and the wind readout,
          // it must stay narrow enough not to run under either at the demo viewport.
          className="prov-panel absolute left-1/2 top-3 max-w-xs -translate-x-1/2 p-2 text-caption text-text-tertiary"
          data-testid="basemap-unavailable-engine"
        >
          Basemap unavailable in this browser — stations are placed by relative position only.
        </p>
      )}
      {basemapAvailable && tilesPresent === false && markers.length > 0 && (
        <p
          className="prov-panel absolute left-1/2 top-3 max-w-xs -translate-x-1/2 p-2 text-caption text-text-tertiary"
          data-testid="basemap-unavailable-tiles"
        >
          Street basemap not fetched — stations are shown on the token ground. Run{" "}
          <code>make basemap</code> for street detail.
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
