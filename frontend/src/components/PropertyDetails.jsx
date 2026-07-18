import React, { useMemo } from "react";
import {
  fmt,
  fmtMoney,
  isPresent,
  getDisplayAddress,
  getLatLon,
  getSovValues,
  getFireAssessment,
  worstBandMeta,
} from "../utils/propertyDetails.js";
import { DetailRow, KeyValueCard, MiniStat } from "./propertyDetails/primitives.jsx";
import FireRiskSection from "./propertyDetails/FireRiskSection.jsx";
import BlockPropertiesTable from "./propertyDetails/BlockPropertiesTable.jsx";
import EmptyDetailsState from "./propertyDetails/EmptyDetailsState.jsx";

/* ========================= MAIN ========================= */

export default function PropertyDetails({
  property,
  selectedBlock = null,
  blockMode = false,
  onSelectProperty,
  legendCounts = null,
}) {
  const activeSource = property || selectedBlock || {};

  const { line1, line2, city, postcode } = useMemo(
    () => getDisplayAddress(property || {}),
    [property]
  );

  const { lat, lon } = useMemo(() => getLatLon(activeSource), [activeSource]);

  const sov = useMemo(() => getSovValues(property || {}), [property]);

  const propertyFire = useMemo(() => getFireAssessment(property), [property]);
  const blockFire = useMemo(() => getFireAssessment(selectedBlock), [selectedBlock]);

  if (!property && !blockMode) {
    return <EmptyDetailsState legendCounts={legendCounts} />;
  }

  if (blockMode && selectedBlock && !property) {
    const rep = selectedBlock.representativeProperty;
    const rawAddr = rep?.address_line_1 || rep?.address || "";
    const blockAddr = rawAddr.replace(/^(flat|apartment|unit|apt)[^,]*,\s*/i, "").trim();
    const blockPostcode = rep?.post_code || rep?.postcode || "";
    const blockAddrDisplay = [blockAddr, blockPostcode].filter(Boolean).join(", ") || selectedBlock.name || selectedBlock.label;
    const blockOverall = worstBandMeta(blockFire.fra, blockFire.fraew);
    // Basement derived from the block's flats (NGD basementpresence): any flat
    // with a basement → Yes; OS captured the building but no basement → No;
    // OS has no data for this building → —.
    const basements = (selectedBlock.properties || []).map((p) => p.basement).filter((b) => typeof b === "boolean");
    const basementLabel = basements.length === 0 ? "—" : basements.some(Boolean) ? "Yes" : "No";

    return (
      <div className="details-body">
        <div className="details-block">
          <div className="row-between" style={{ alignItems: "flex-start", gap: 8 }}>
            <div style={{ fontSize: 16, fontWeight: 800, lineHeight: 1.25, letterSpacing: "-0.01em" }}>{blockAddrDisplay}</div>
            <span className={`pill ${blockOverall.cls}`} style={{ whiteSpace: "nowrap" }}>{blockOverall.label}</span>
          </div>
          <div className="details-sub" style={{ marginTop: 3 }}>
            Block {selectedBlock.block_reference || selectedBlock.name}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 12 }}>
            <MiniStat
              label="Total insured"
              value={
                isPresent(selectedBlock.totalValue)
                  ? fmtMoney(selectedBlock.totalValue)
                  : isPresent(selectedBlock.total_sum_insured)
                  ? fmtMoney(selectedBlock.total_sum_insured)
                  : "—"
              }
            />
            <MiniStat label="Properties" value={selectedBlock.count ?? selectedBlock.unit_count} />
            <MiniStat
              label="Max height"
              value={
                Number.isFinite(Number(selectedBlock.maxHeight)) && Number(selectedBlock.maxHeight) > 0
                  ? `${fmt(selectedBlock.maxHeight, 1)} m`
                  : Number.isFinite(Number(selectedBlock.max_storeys))
                  ? `${selectedBlock.max_storeys} st.`
                  : "—"
              }
            />
            <MiniStat label="UPRN" value={isPresent(selectedBlock.parent_uprn) ? selectedBlock.parent_uprn : "—"} />
            <MiniStat label="Basement" value={basementLabel} />
          </div>

          {Number.isFinite(lat) && Number.isFinite(lon) ? (
            <div className="details-sub" style={{ marginTop: 10 }}>Coordinates: {fmt(lat, 5)}, {fmt(lon, 5)}</div>
          ) : null}
        </div>

        <FireRiskSection
          fra={blockFire.fra}
          fraew={blockFire.fraew}
          emptyLabel={
            selectedBlock.asset_type === "standalone" &&
            ["house", "bungalow"].includes(selectedBlock.dwelling_form)
              ? "FRA / FRAEW not required — standalone single-household dwelling."
              : "No FRA / FRAEW data linked to this block."
          }
        />

        <BlockPropertiesTable properties={selectedBlock.properties || []} onSelectProperty={onSelectProperty} />
      </div>
    );
  }

  if (!property) {
    return <EmptyDetailsState legendCounts={legendCounts} />;
  }

  return (
    <div className="details-body">
      <div className="details-block">
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
          <div className="details-h" style={{ marginBottom: 0 }}>
            {[line1, line2].filter(Boolean).join(" ") || "—"}
          </div>
          {selectedBlock && (
            <button
              onClick={() => onSelectProperty?.(null)}
              style={{
                flexShrink: 0,
                fontSize: 12,
                padding: "3px 10px",
                borderRadius: 6,
                border: "1px solid var(--border, #e2e8f0)",
                background: "var(--panel, #fff)",
                color: "var(--text-light, #64748b)",
                cursor: "pointer",
                fontWeight: 500,
              }}
            >
              ← Block view
            </button>
          )}
        </div>

        <DetailRow
          label="Property ref"
          value={property?.property_reference ?? property?.propertyReference ?? property?.id}
        />
        <DetailRow label="Property ID" value={property?.property_id ?? property?.propertyId} />
        <DetailRow
          label="Block"
          value={
            property?.is_standalone === true
              ? "Standalone dwelling — not part of a block"
              : property?.block_reference ??
                selectedBlock?.label ??
                selectedBlock?.name ??
                selectedBlock?.block_reference
          }
        />
      </div>

      <div className="details-block">
        <div className="details-h">SOV</div>

        <div className="kv-grid">
          <KeyValueCard
            label="Sum insured"
            value={Number.isFinite(sov.sumInsured) ? fmtMoney(sov.sumInsured) : "—"}
          />
          <KeyValueCard label="Property type" value={sov.propertyType} />
          <KeyValueCard label="Occupancy" value={sov.occupancy} />
          <KeyValueCard
            label="Height"
            value={Number.isFinite(sov.height) ? `${fmt(sov.height, 1)} m` : "—"}
          />
          <KeyValueCard
            label="Storeys"
            value={Number.isFinite(sov.storeys) ? sov.storeys : "—"}
          />
          <KeyValueCard
            label="Year built"
            value={Number.isFinite(sov.yearBuilt) ? sov.yearBuilt : "—"}
          />
          <KeyValueCard label="UPRN" value={property?.uprn ?? property?.UPRN} />
          <KeyValueCard label="Parent UPRN" value={property?.parent_uprn} />
          {isPresent(property?.flood_risk_band) ? (
            <KeyValueCard label="Flood risk" value={property.flood_risk_band} />
          ) : null}
        </div>
      </div>

      <FireRiskSection
        fra={propertyFire.fra}
        fraew={propertyFire.fraew}
        emptyLabel={
          property?.is_standalone === true &&
          ["house", "bungalow"].includes(property?.dwelling_form)
            ? "FRA / FRAEW not required — standalone single-household dwelling."
            : "No FRA / FRAEW data linked to this property."
        }
      />
    </div>
  );
}
