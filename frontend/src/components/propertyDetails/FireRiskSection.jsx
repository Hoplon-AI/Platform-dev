// FRA / FRAEW fire risk panel for PropertyDetails.
import React from "react";
import { FactGrid, ChipRow, Chip, BulletList, MiniStat, MeasureHead } from "./primitives.jsx";
import {
  bandMeta,
  normaliseBooleanLabel,
  normaliseFraActions,
  getFraewHeight,
  prettyText,
  fmt,
  truncate,
  asArray,
} from "../../utils/propertyDetails.js";

export default function FireRiskSection({
  fra,
  fraew,
  emptyLabel = "No FRA / FRAEW data linked.",
}) {
  const fraMeta = bandMeta(
    fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating
  );
  const fraewMeta = bandMeta(
    fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating
  );
  const fraActions = normaliseFraActions(fra);
  const fraewRecommendations = asArray(
    fraew?.recommendations ?? fraew?.actions ?? fraew?.remedial_actions
  );
  const fraewHeight = getFraewHeight(fraew);

  return (
    <div className="details-block">
      <div className="details-h">Fire Risk Assessment (FRA / FRAEW)</div>

      {!fra && !fraew && <div className="muted">{emptyLabel}</div>}

      {(fra || fraew) && (
        <div
          style={{
            display: "grid",
            gap: 12,
          }}
        >
          {fra && (
            <div
              style={{
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: 12,
                padding: 12,
                background: "#fff",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  flexWrap: "wrap",
                  marginBottom: 8,
                }}
              >
                <span className={`pill ${fraMeta.cls}`}>{fraMeta.label}</span>
                <span className="pill pill-muted">FRA</span>
                {fra.extraction_confidence ? (
                  <span className="pill pill-muted">
                    confidence {fmt(fra.extraction_confidence, 2)}
                  </span>
                ) : null}
              </div>

              <FactGrid
                items={[
                  { label: "Risk", value: fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating },
                  { label: "Assessment date", value: fra?.assessment_date },
                  { label: "Valid until", value: fra?.assessment_valid_until },
                  { label: "Next review", value: fra?.next_review_date },
                  { label: "In date", value: normaliseBooleanLabel(fra?.is_in_date) },
                  { label: "Assessor", value: fra?.assessor_name },
                  { label: "Company", value: fra?.assessor_company },
                  { label: "Responsible person", value: fra?.responsible_person },
                  { label: "Evacuation", value: fra?.evacuation_strategy ? prettyText(fra.evacuation_strategy) : null },
                ]}
              />
              <MeasureHead>Fire safety measures</MeasureHead>
              <ChipRow>
                <Chip label="Sprinklers" value={fra?.has_sprinkler_system ?? fra?.sprinkler_system} />
                <Chip label="Smoke detection" value={fra?.has_smoke_detection ?? fra?.smoke_detection} />
                <Chip label="Fire alarm" value={fra?.has_fire_alarm_system ?? fra?.fire_alarm_system} />
                <Chip label="Fire doors" value={fra?.has_fire_doors ?? fra?.fire_doors} />
                <Chip label="Compartmentation" value={fra?.has_compartmentation ?? fra?.compartmentation} />
              </ChipRow>

              <MeasureHead>Remedial actions</MeasureHead>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
                <MiniStat label="Total" value={fraActions.total} />
                <MiniStat label="Overdue" value={fraActions.overdue} tone={Number(fraActions.overdue) > 0 ? "red" : "default"} />
                <MiniStat label="Outstanding" value={fraActions.outstanding} tone={Number(fraActions.outstanding) > 0 ? "amber" : "default"} />
              </div>

              {fra.summary ? (
                <div className="details-sub" style={{ marginTop: 10 }}>
                  <b>Summary:</b> {truncate(fra.summary, 240)}
                </div>
              ) : null}

              <BulletList items={fraActions.items} />
            </div>
          )}

          {fraew && (
            <div
              style={{
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: 12,
                padding: 12,
                background: "#fff",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  flexWrap: "wrap",
                  marginBottom: 8,
                }}
              >
                <span className={`pill ${fraewMeta.cls}`}>{fraewMeta.label}</span>
                <span className="pill pill-muted">FRAEW</span>
                {fraew.extraction_confidence ? (
                  <span className="pill pill-muted">
                    confidence {fmt(fraew.extraction_confidence, 2)}
                  </span>
                ) : null}
              </div>

              <FactGrid
                items={[
                  { label: "Risk", value: fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating },
                  { label: "External wall risk", value: fraew?.external_wall_risk ?? fraew?.building_risk_rating },
                  { label: "Assessment date", value: fraew?.assessment_date },
                  { label: "Valid until", value: fraew?.assessment_valid_until },
                  { label: "In date", value: normaliseBooleanLabel(fraew?.is_in_date) },
                  { label: "Height", value: Number.isFinite(fraewHeight) ? `${fmt(fraewHeight, 1)} m` : "—" },
                  { label: "Height category", value: fraew?.building_height_category ? String(fraew.building_height_category).replace(/_/g, " ") : null },
                  { label: "Storeys", value: fraew?.num_storeys },
                  { label: "Units", value: fraew?.num_units },
                  { label: "Cladding type", value: fraew?.cladding_type },
                  {
                    label: "Wall types",
                    value: (() => {
                      let wt = fraew?.wall_types;
                      if (typeof wt === "string") { try { wt = JSON.parse(wt); } catch { return wt; } }
                      if (!Array.isArray(wt) || wt.length === 0) return "—";
                      return wt.map((w) => w?.type_ref ?? w).filter(Boolean).join(", ");
                    })(),
                  },
                ]}
              />
              <MeasureHead>Cladding & protections</MeasureHead>
              <ChipRow>
                <Chip label="Combustible cladding" value={fraew?.has_combustible_cladding ?? fraew?.combustible_cladding} hazard />
                <Chip label="Cavity barriers" value={fraew?.cavity_barriers_present} />
                <Chip label="PAS 9980 compliant" value={fraew?.pas_9980_compliant} />
                <Chip label="Dry riser" value={fraew?.dry_riser_present} />
                <Chip label="Wet riser" value={fraew?.wet_riser_present} />
              </ChipRow>
              <FactGrid
                items={[
                  { label: "PAS 9980 version", value: fraew?.pas_9980_version },
                  { label: "Interim measures", value: normaliseBooleanLabel(fraew?.interim_measures_required, "Required", "Not required") },
                  { label: "Interim detail", value: fraew?.interim_measures_detail },
                  { label: "Remediation required", value: normaliseBooleanLabel(fraew?.remediation_required ?? fraew?.has_remedial_actions) },
                  { label: "Evacuation", value: fraew?.evacuation_strategy ? prettyText(fraew.evacuation_strategy) : null },
                  { label: "ADB compliant", value: fraew?.adb_compliant ? prettyText(fraew.adb_compliant) : null },
                ]}
              />

              {fraew.summary ? (
                <div className="details-sub" style={{ marginTop: 10 }}>
                  <b>Summary:</b> {truncate(fraew.summary, 240)}
                </div>
              ) : null}

              <BulletList items={fraewRecommendations} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
