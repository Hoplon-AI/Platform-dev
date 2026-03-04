# Building Safety Feature Extraction Specifications

This document provides detailed specifications for extracting building safety-related features from documents (FRAEW, FRA, SCR, FRSA, and other building safety documents) using agentic extraction with AWS Bedrock and Claude models.

## 1. Building Safety Act 2022 Compliance Indicators

### Purpose
Identify whether and how documents reference compliance with the Building Safety Act 2022, which is the primary UK legislation governing building safety for high-rise residential buildings.

### Fields to Extract:

**`building_safety_act_2022_mentioned`** (boolean)
- Whether the Building Safety Act 2022 is explicitly mentioned
- Keywords: "Building Safety Act 2022", "Building Safety Act", "BSA 2022"

**`building_safety_act_compliance_status`** (string, enum)
- Values: "COMPLIANT", "NON_COMPLIANT", "PARTIALLY_COMPLIANT", "UNDER_REVIEW", "NOT_SPECIFIED"
- Extract from explicit statements about compliance status

**`part_4_duties_mentioned`** (boolean)
- Whether Part 4 duties are mentioned (Part 4 covers Accountable Person duties)
- Keywords: "Part 4", "Part 4 duties", "Part 4 of the Building Safety Act"

**`part_4_duties_list`** (array of strings)
- Specific Part 4 duties mentioned:
  - "Identifying and assessing building safety risks"
  - "Managing building safety risks"
  - "Providing building safety information"
  - "Engaging with customers"
  - "Managing complaints"
  - "Consultation with relevant persons"
  - "Decision making process documentation"

**`building_safety_decisions_mentioned`** (boolean)
- Whether building safety decisions are discussed
- Context: Decisions relating to fire safety or structural management

**`building_safety_decisions_list`** (array of objects)
- Each decision object contains:
  - `decision_type` (string): e.g., "remediation work", "evacuation strategy change", "material alteration"
  - `decision_date` (date, optional)
  - `decision_description` (text, optional)
  - `consultation_required` (boolean)
  - `consultation_conducted` (boolean, optional)

**`building_safety_regulator_mentioned`** (boolean)
- Whether Building Safety Regulator (BSR) is mentioned
- Keywords: "Building Safety Regulator", "BSR", "regulator"

**`building_safety_case_report_mentioned`** (boolean)
- Whether Building Safety Case Report is mentioned
- Keywords: "Building Safety Case", "Safety Case Report", "BSR submission"

**`building_a_safer_future_charter`** (object, optional)
- `charter_mentioned` (boolean)
- `charter_status` (string): "CHAMPION", "MEMBER", "SIGNATORY", "NOT_MENTIONED"
- `charter_date` (date, optional)

### Extraction Hints:
- Look for phrases like "in accordance with Building Safety Act 2022"
- Check for explicit compliance statements
- Identify duty references (e.g., "our Part 4 duties include...")
- Extract decision-making processes and documentation requirements

---

## 2. Principle Accountable Person Information

### Purpose
Identify who is designated as the Principle Accountable Person (PAP) for the building, as required by Building Safety Act 2022.

### Fields to Extract:

**`principle_accountable_person_mentioned`** (boolean)
- Whether PAP is explicitly mentioned
- Keywords: "Principle Accountable Person", "PAP", "Accountable Person", "responsible person"

**`principle_accountable_person_name`** (string)
- Name of the individual or organization designated as PAP
- Examples: "Salix Homes", "[Housing Association Name]"

**`principle_accountable_person_type`** (string, enum)
- Values: "ORGANISATION", "INDIVIDUAL", "NOT_SPECIFIED"
- Distinguish between individual person vs organization

**`principle_accountable_person_contact`** (object, optional)
- `email` (string, optional)
- `phone` (string, optional)
- `address` (text, optional)

**`accountable_person_duties_mentioned`** (boolean)
- Whether specific duties of the Accountable Person are listed

**`accountable_person_duties`** (array of strings)
- List of duties mentioned:
  - "Managing fire safety risks"
  - "Managing structural safety risks"
  - "Building safety risk assessment"
  - "Customer engagement"
  - "Information sharing"

### Extraction Hints:
- Look for explicit statements like "X is the Principle Accountable Person"
- Check for "responsible for managing fire and structural safety risks"
- Extract contact information if provided
- Identify specific duties and responsibilities mentioned

---

## 3. Mandatory Occurrence Report References

### Purpose
Identify references to Mandatory Occurrence Reports (MORs), which are required when building safety concerns are identified.

### Fields to Extract:

**`mandatory_occurrence_report_mentioned`** (boolean)
- Whether MOR is mentioned
- Keywords: "Mandatory Occurrence Report", "MOR", "occurrence report", "building safety concern report"

**`mandatory_occurrence_reports`** (array of objects)
- Each MOR object contains:
  - `report_id` (string, optional): Reference number or identifier
  - `report_date` (date, optional)
  - `report_type` (string, optional): Type of safety concern
  - `concern_description` (text, optional): What was reported
  - `status` (string, enum, optional): "SUBMITTED", "INVESTIGATING", "RESOLVED", "ONGOING"
  - `reported_by` (string, optional): Who made the report (customer, employee, contractor)
  - `building_affected` (string, optional): Which building(s) affected

**`mandatory_occurrence_reporting_process_mentioned`** (boolean)
- Whether the process for reporting is described

**`mandatory_occurrence_reporting_channels`** (array of strings)
- Methods mentioned for reporting:
  - "Building Safety letter boxes"
  - "Email: buildingsafety@..."
  - "Phone: 0800..."
  - "Website form"
  - "In-person reporting"

**`mandatory_occurrence_report_triggers`** (array of strings)
- What triggers an MOR:
  - "Poor installation or workmanship"
  - "Customer DIY causing damage"
  - "Safety feature damaged or not working"
  - "Significant building safety risk identified"

### Extraction Hints:
- Look for explicit MOR references with dates/IDs
- Extract reporting mechanisms and contact details
- Identify what types of concerns trigger reports
- Note any performance metrics or targets mentioned

---

## 4. Building Safety Regulator Interactions

### Purpose
Identify any interactions, communications, or submissions to the Building Safety Regulator (BSR).

### Fields to Extract:

**`building_safety_regulator_mentioned`** (boolean)
- Whether BSR is mentioned
- Keywords: "Building Safety Regulator", "BSR", "regulator", "Building Safety Regulator (BSR)"

**`bsr_interactions`** (array of objects)
- Each interaction contains:
  - `interaction_type` (string, enum): "SUBMISSION", "CONSULTATION", "NOTIFICATION", "COMPLAINT_APPEAL", "INFORMATION_REQUEST"
  - `interaction_date` (date, optional)
  - `interaction_subject` (text, optional): What was the interaction about
  - `interaction_status` (string, optional): "PENDING", "COMPLETED", "UNDER_REVIEW"

**`bsr_submissions`** (array of objects)
- Specific submissions to BSR:
  - `submission_type` (string): "Building Safety Case Report", "Mandatory Occurrence Report", "Safety Information", "Compliance Documentation"
  - `submission_date` (date, optional)
  - `submission_status` (string, optional)

**`bsr_complaint_appeals`** (array of objects, optional)
- Complaints or appeals to BSR:
  - `appeal_date` (date, optional)
  - `appeal_reason` (text, optional)
  - `appeal_status` (string, optional)

**`bsr_contact_information`** (object, optional)
- `website` (string, optional): e.g., "www.gov.uk/guidance/contact-the-building-safety-regulator"
- `email` (string, optional)
- `phone` (string, optional)

### Extraction Hints:
- Look for explicit mentions of BSR submissions or communications
- Extract dates and types of interactions
- Note any BSR contact information provided
- Identify complaint/appeal processes to BSR

---

## 5. Customer Engagement Strategy Elements

### Purpose
Extract information about how the organization engages with customers/residents on building safety matters.

### Fields to Extract:

**`customer_engagement_strategy_mentioned`** (boolean)
- Whether a customer engagement strategy is mentioned
- Keywords: "Customer Engagement Strategy", "Building Safety Customer Engagement Strategy", "Methods of Engagement"

**`engagement_strategy_version`** (string, optional)
- Version number or date of strategy
- Example: "Version Four (updated October 2025)"

**`engagement_strategy_review_frequency`** (string, optional)
- How often strategy is reviewed
- Example: "every two years"

**`engagement_methods`** (array of strings)
- Methods mentioned:
  - "Letters"
  - "Emails"
  - "Text messages"
  - "Telephone calls"
  - "Face-to-face conversations"
  - "Newsletters"
  - "Website"
  - "Customer portal"
  - "Social media"
  - "Videos"
  - "Notice boards"
  - "Drop-in sessions"
  - "Surgeries"
  - "Block walkabouts"
  - "Apartment Living Forum"
  - "WIN Days (Working in Neighbourhood)"

**`engagement_forums`** (array of objects)
- Specific forums or groups:
  - `forum_name` (string): e.g., "Apartment Living Forum"
  - `meeting_frequency` (string, optional): e.g., "every six months"
  - `purpose` (text, optional)
  - `contact_email` (string, optional)

**`consultation_stages`** (array of objects, optional)
- For major works, consultation stages:
  - `stage_name` (string): "Alerting", "Procurement", "Design", "Building work", "Completion"
  - `consultation_details` (text, optional): What information is shared at this stage

**`customer_feedback_channels`** (array of objects)
- How customers can provide feedback:
  - `channel_type` (string): "email", "phone", "website", "letter_box", "in_person"
  - `contact_details` (string, optional)
  - `purpose` (text, optional)

**`accessibility_measures`** (array of strings, optional)
- Accessibility features mentioned:
  - "Recite Me tool"
  - "Translation services"
  - "Large text options"
  - "Screen reader support"
  - "Audio files"
  - "Multiple languages"

### Extraction Hints:
- Look for explicit strategy documents or references
- Extract all communication channels mentioned
- Identify forums, panels, or engagement groups
- Note accessibility and language support
- Extract contact information for engagement

---

## 6. High-Rise Building Indicators

### Purpose
Identify whether the document relates to high-rise buildings and extract relevant high-rise specific information.

### Fields to Extract:

**`high_rise_building_mentioned`** (boolean)
- Whether high-rise is mentioned
- Keywords: "high rise", "high-rise", "tower block", "high rise building", "tall building"

**`building_height_category`** (string, enum, optional)
- Values: "HIGH_RISE" (18m+ or 7+ storeys), "MEDIUM_RISE", "LOW_RISE", "NOT_SPECIFIED"
- Based on height or storey count mentioned

**`number_of_storeys`** (integer, optional)
- Number of storeys/floors mentioned

**`building_height_metres`** (number, optional)
- Height in metres if specified

**`number_of_high_rise_buildings`** (integer, optional)
- If document mentions multiple buildings, count

**`high_rise_building_names`** (array of strings, optional)
- Names of specific high-rise buildings mentioned

**`high_rise_specific_measures`** (array of strings, optional)
- High-rise specific safety measures:
  - "Enhanced fire safety systems"
  - "Dedicated Property Safety Officers"
  - "Regular high-rise inspections"
  - "Block-specific Methods of Engagement"
  - "High Rise Month of Action"

**`building_safety_act_applicable`** (boolean)
- Whether Building Safety Act 2022 applies (typically for 18m+ or 7+ storeys)

### Extraction Hints:
- Look for explicit height or storey counts
- Identify high-rise specific terminology
- Extract building names and counts
- Note high-rise specific safety measures mentioned

---

## 7. Evacuation Strategies

### Purpose
Extract information about evacuation strategies and procedures for the building.

### Fields to Extract:

**`evacuation_strategy_mentioned`** (boolean)
- Whether evacuation strategy is discussed
- Keywords: "evacuation strategy", "evacuation procedure", "evacuation plan", "stay put", "stay safe"

**`evacuation_strategy_type`** (string, enum)
- Values: "STAY_PUT", "STAY_SAFE", "SIMULTANEOUS", "PHASED", "DEFEND_IN_PLACE", "FULL_EVACUATION", "NOT_SPECIFIED"
- "STAY_PUT" and "STAY_SAFE" are typically the same

**`evacuation_strategy_description`** (text, optional)
- Detailed description of what the strategy means
- Example: "If fire in your flat, leave. If fire elsewhere, remain in flat."

**`evacuation_strategy_changed`** (boolean, optional)
- Whether strategy has changed or is subject to change

**`evacuation_strategy_change_reason`** (text, optional)
- Why strategy changed (e.g., "fire engineer recommendation", "building safety risk identified")

**`evacuation_strategy_consultation_required`** (boolean)
- Whether consultation is required before changing strategy
- Note: Strategy changes may NOT require consultation if on fire engineer advice

**`evacuation_instructions`** (text, optional)
- Specific instructions provided to residents
- What to do in different scenarios

**`evacuation_assembly_points`** (array of strings, optional)
- Location of assembly points if mentioned

**`personal_evacuation_plans_mentioned`** (boolean)
- Whether Personal Emergency Evacuation Plans (PEEPs) or Personal Centric Fire Risk Assessments (PCFRAs) are mentioned

**`evacuation_support_required`** (boolean, optional)
- Whether residents need support to evacuate
- Related to disabilities or additional needs

**`fire_service_evacuation_instructions`** (text, optional)
- Instructions about following fire service directions
- Example: "Always evacuate if asked by firefighters"

### Extraction Hints:
- Look for explicit strategy statements
- Extract detailed instructions and procedures
- Note any changes or potential changes
- Identify support requirements for vulnerable residents
- Extract assembly point locations

---

## 8. Fire Safety Measures

### Purpose
Extract comprehensive information about fire safety measures, systems, and equipment in place.

### Fields to Extract:

**`fire_safety_measures_mentioned`** (boolean)
- Whether fire safety measures are discussed

**`fire_safety_systems`** (array of objects)
- Each system contains:
  - `system_type` (string): "FIRE_ALARM", "SMOKE_DETECTORS", "HEAT_DETECTORS", "SPRINKLERS", "FIRE_DOORS", "FIRE_EXTINGUISHERS", "FIRE_HOSES", "EMERGENCY_LIGHTING", "VENTILATION_SYSTEMS"
  - `system_status` (string, optional): "OPERATIONAL", "UNDER_MAINTENANCE", "NEEDS_REPAIR", "NOT_SPECIFIED"
  - `inspection_frequency` (string, optional): How often checked
  - `last_inspection_date` (date, optional)
  - `location` (string, optional): Where system is located (communal, individual flats, etc.)

**`fire_doors_mentioned`** (boolean)
- Whether fire doors are discussed

**`fire_doors_details`** (object, optional)
- `fire_doors_present` (boolean)
- `fire_doors_locations` (array of strings): "communal areas", "flat entrance doors", "stairwells"
- `fire_doors_self_closing` (boolean, optional)
- `fire_doors_maintenance_required` (boolean, optional)
- `fire_doors_tampering_warning` (boolean, optional): Warnings about not propping open or tampering

**`fire_alarm_systems`** (object, optional)
- `alarm_type` (string, optional)
- `alarm_testing_frequency` (string, optional)
- `alarm_coverage` (string, optional): "communal only", "communal and flats", "full building"

**`smoke_heat_detectors`** (object, optional)
- `detector_types` (array of strings): "smoke detectors", "heat detectors"
- `detector_locations` (array of strings): "communal areas", "individual flats", "both"
- `testing_frequency` (string, optional)
- `maintenance_required` (boolean, optional)

**`sprinkler_systems`** (object, optional)
- `sprinklers_present` (boolean)
- `sprinkler_coverage` (string, optional): "full building", "communal only", "partial"
- `sprinkler_maintenance` (string, optional)

**`fire_safety_equipment_checks`** (array of objects, optional)
- Regular checks mentioned:
  - `equipment_type` (string)
  - `check_frequency` (string, optional)
  - `responsible_party` (string, optional): Who performs checks

**`fire_safety_notices`** (object, optional)
- `notices_present` (boolean)
- `notice_locations` (array of strings): "lobby areas", "communal areas", "each floor"
- `notice_content_types` (array of strings): "fire assembly points", "evacuation procedures", "fire safety instructions"

**`fire_safety_information_provided`** (array of strings, optional)
- Types of information provided:
  - "Home Safety Guide"
  - "Fire safety instructions"
  - "Evacuation procedures"
  - "Fire safety measures summary"

**`fire_safety_officers_mentioned`** (boolean)
- Whether dedicated fire safety officers or Property Safety Officers are mentioned

**`fire_safety_officer_details`** (object, optional)
- `officer_role` (string, optional): "Property Safety Officer", "Fire Safety Officer", "Building Safety Officer"
- `officer_responsibilities` (array of strings, optional)
- `officer_contact` (object, optional)

### Extraction Hints:
- Look for comprehensive lists of fire safety systems
- Extract inspection and maintenance schedules
- Identify locations of equipment
- Note any warnings or requirements about equipment
- Extract contact information for fire safety personnel

---

## 9. Structural Integrity Mentions

### Purpose
Identify references to structural safety, building structure, and structural assessments.

### Fields to Extract:

**`structural_integrity_mentioned`** (boolean)
- Whether structural integrity or structural safety is discussed
- Keywords: "structural integrity", "structural safety", "structural stability", "building structure", "structural soundness"

**`structural_assessments_mentioned`** (boolean)
- Whether structural assessments or surveys are mentioned

**`structural_assessments`** (array of objects, optional)
- Each assessment contains:
  - `assessment_type` (string): "Type 4 Risk Assessment", "Structural Survey", "Structural Inspection", "Building Safety Risk Assessment"
  - `assessment_date` (date, optional)
  - `assessor_company` (string, optional)
  - `assessment_findings` (text, optional): Summary of findings
  - `structural_issues_identified` (boolean, optional)
  - `structural_issues_description` (text, optional)

**`structural_risks_mentioned`** (boolean)
- Whether structural risks are identified

**`structural_risks`** (array of objects, optional)
- Each risk contains:
  - `risk_type` (string, optional): e.g., "foundation issues", "wall stability", "roof structure"
  - `risk_severity` (string, optional): "HIGH", "MEDIUM", "LOW"
  - `risk_description` (text, optional)
  - `remediation_required` (boolean, optional)

**`structural_work_mentioned`** (boolean)
- Whether structural work or remediation is mentioned

**`structural_work_details`** (array of objects, optional)
- Work items:
  - `work_type` (string): "remediation", "strengthening", "repair", "replacement"
  - `work_description` (text, optional)
  - `work_status` (string, optional): "PLANNED", "IN_PROGRESS", "COMPLETED"
  - `work_date` (date, optional)

**`building_materials_mentioned`** (boolean)
- Whether building materials affecting structure are mentioned

**`building_materials`** (array of strings, optional)
- Materials mentioned: "concrete", "steel", "masonry", "timber", "cladding", "external wall system"

**`structural_maintenance_required`** (boolean, optional)
- Whether ongoing structural maintenance is mentioned

### Extraction Hints:
- Look for explicit structural assessment references
- Extract assessment types and dates
- Identify structural risks and their severity
- Note any structural work or remediation
- Extract building material information

---

## 10. Maintenance Requirements

### Purpose
Extract information about maintenance schedules, requirements, and maintenance-related building safety measures.

### Fields to Extract:

**`maintenance_mentioned`** (boolean)
- Whether maintenance is discussed
- Keywords: "maintenance", "inspection", "repair", "upkeep", "servicing"

**`maintenance_schedules_mentioned`** (boolean)
- Whether maintenance schedules are provided

**`maintenance_schedules`** (array of objects, optional)
- Each schedule contains:
  - `maintenance_type` (string): "fire safety equipment", "structural", "communal areas", "ventilation", "electrical", "general building"
  - `frequency` (string, optional): "daily", "weekly", "monthly", "quarterly", "annually", "as required"
  - `responsible_party` (string, optional): Who performs maintenance
  - `last_maintenance_date` (date, optional)
  - `next_maintenance_date` (date, optional)

**`maintenance_checks_mentioned`** (boolean)
- Whether specific maintenance checks are listed

**`maintenance_checks`** (array of objects, optional)
- Specific checks:
  - `check_type` (string): e.g., "smoke detector testing", "fire door inspection", "ventilation cleaning", "electrical socket check"
  - `check_frequency` (string, optional)
  - `check_location` (string, optional): "communal", "individual flats", "both"

**`tenancy_audits_mentioned`** (boolean)
- Whether tenancy audits or safety checks in individual properties are mentioned

**`tenancy_audit_details`** (object, optional)
- `audit_frequency` (string, optional)
- `audit_scope` (array of strings, optional):
  - "Testing smoke and heat detectors"
  - "Checking windows and front door"
  - "Checking ventilation systems"
  - "Visual inspection of electrical sockets"
  - "Contact details verification"
  - "Evacuation capability assessment"
  - "Fire safety information provision"

**`communal_area_maintenance`** (object, optional)
- `communal_maintenance_mentioned` (boolean)
- `communal_safety_audits` (boolean, optional)
- `communal_clearance_requirements` (boolean, optional): Requirements to keep communal areas clear
- `communal_fire_door_maintenance` (boolean, optional)

**`maintenance_backlog_mentioned`** (boolean, optional)
- Whether maintenance backlog or outstanding repairs are mentioned

**`maintenance_priorities`** (array of strings, optional)
- Priority maintenance items or urgent repairs

**`maintenance_budget_mentioned`** (boolean, optional)
- Whether maintenance budgets or investment programmes are mentioned

### Extraction Hints:
- Look for explicit maintenance schedules and frequencies
- Extract specific check types and locations
- Identify responsible parties
- Note tenancy audit processes
- Extract communal area maintenance requirements

---

## 11. Emergency Procedures

### Purpose
Extract comprehensive information about emergency procedures, what to do in emergencies, and emergency preparedness.

### Fields to Extract:

**`emergency_procedures_mentioned`** (boolean)
- Whether emergency procedures are discussed
- Keywords: "emergency procedures", "emergency", "what to do in event of fire", "emergency plan"

**`emergency_contact_information`** (object, optional)
- `fire_service` (string, optional): "999 and ask for fire"
- `building_safety_team_email` (string, optional)
- `building_safety_team_phone` (string, optional)
- `emergency_line` (string, optional)

**`fire_emergency_instructions`** (text, optional)
- Detailed instructions for fire emergencies
- What to do step-by-step

**`emergency_scenarios_covered`** (array of strings, optional)
- Types of emergencies:
  - "Fire in your flat"
  - "Fire elsewhere in building"
  - "Smoke in building"
  - "Fire alarm activation"
  - "Other emergencies"

**`emergency_assembly_points`** (array of strings, optional)
- Where to assemble in emergency
- Locations mentioned

**`emergency_communication_methods`** (array of strings, optional)
- How emergency information is communicated:
  - "Fire safety notices"
  - "Alarm systems"
  - "Direct communication"
  - "Emergency broadcasts"

**`personal_emergency_evacuation_plans`** (object, optional)
- `peeps_mentioned` (boolean): Personal Emergency Evacuation Plans
- `pcfra_mentioned` (boolean): Personal Centric Fire Risk Assessments
- `support_required_assessment` (boolean, optional): Whether assessment of evacuation support needs is mentioned

**`emergency_access_requirements`** (object, optional)
- `access_for_emergency_works` (boolean, optional): Whether emergency access without notice is mentioned
- `access_notice_period` (string, optional): Normal notice period (e.g., "48 hours")
- `emergency_access_justification` (text, optional): When emergency access is allowed

**`emergency_equipment_locations`** (array of strings, optional)
- Where emergency equipment is located
- Fire extinguishers, fire hoses, emergency exits, etc.

**`emergency_testing_mentioned`** (boolean, optional)
- Whether emergency procedure testing or drills are mentioned

**`emergency_testing_frequency`** (string, optional)
- How often emergency procedures are tested

### Extraction Hints:
- Look for explicit "what to do" instructions
- Extract step-by-step emergency procedures
- Identify different emergency scenarios
- Note assembly points and exit routes
- Extract emergency contact information
- Identify support requirements for vulnerable residents

---

## Feature Extraction JSON Schema Structure

The agentic extraction should output features in the following structure:

```json
{
  "building_safety_act_2022": {
    "building_safety_act_2022_mentioned": true,
    "building_safety_act_compliance_status": "COMPLIANT",
    "part_4_duties_mentioned": true,
    "part_4_duties_list": [...],
    "building_safety_decisions_mentioned": true,
    "building_safety_decisions_list": [...],
    "building_safety_regulator_mentioned": true,
    "building_safety_case_report_mentioned": true,
    "building_a_safer_future_charter": {...}
  },
  "principle_accountable_person": {
    "principle_accountable_person_mentioned": true,
    "principle_accountable_person_name": "Salix Homes",
    "principle_accountable_person_type": "ORGANISATION",
    "principle_accountable_person_contact": {...},
    "accountable_person_duties": [...]
  },
  "mandatory_occurrence_reports": {
    "mandatory_occurrence_report_mentioned": true,
    "mandatory_occurrence_reports": [...],
    "mandatory_occurrence_reporting_process_mentioned": true,
    "mandatory_occurrence_reporting_channels": [...],
    "mandatory_occurrence_report_triggers": [...]
  },
  "building_safety_regulator": {
    "building_safety_regulator_mentioned": true,
    "bsr_interactions": [...],
    "bsr_submissions": [...],
    "bsr_contact_information": {...}
  },
  "customer_engagement": {
    "customer_engagement_strategy_mentioned": true,
    "engagement_strategy_version": "Version Four",
    "engagement_methods": [...],
    "engagement_forums": [...],
    "consultation_stages": [...],
    "customer_feedback_channels": [...],
    "accessibility_measures": [...]
  },
  "high_rise_indicators": {
    "high_rise_building_mentioned": true,
    "building_height_category": "HIGH_RISE",
    "number_of_storeys": 20,
    "number_of_high_rise_buildings": 20,
    "high_rise_building_names": [...],
    "high_rise_specific_measures": [...]
  },
  "evacuation_strategy": {
    "evacuation_strategy_mentioned": true,
    "evacuation_strategy_type": "STAY_PUT",
    "evacuation_strategy_description": "...",
    "evacuation_instructions": "...",
    "evacuation_assembly_points": [...],
    "personal_evacuation_plans_mentioned": true,
    "evacuation_support_required": true
  },
  "fire_safety_measures": {
    "fire_safety_measures_mentioned": true,
    "fire_safety_systems": [...],
    "fire_doors_details": {...},
    "fire_alarm_systems": {...},
    "smoke_heat_detectors": {...},
    "fire_safety_equipment_checks": [...],
    "fire_safety_notices": {...},
    "fire_safety_information_provided": [...],
    "fire_safety_officers_mentioned": true,
    "fire_safety_officer_details": {...}
  },
  "structural_integrity": {
    "structural_integrity_mentioned": true,
    "structural_assessments": [...],
    "structural_risks": [...],
    "structural_work_details": [...],
    "building_materials": [...],
    "structural_maintenance_required": true
  },
  "maintenance_requirements": {
    "maintenance_mentioned": true,
    "maintenance_schedules": [...],
    "maintenance_checks": [...],
    "tenancy_audits_mentioned": true,
    "tenancy_audit_details": {...},
    "communal_area_maintenance": {...},
    "maintenance_priorities": [...]
  },
  "emergency_procedures": {
    "emergency_procedures_mentioned": true,
    "emergency_contact_information": {...},
    "fire_emergency_instructions": "...",
    "emergency_scenarios_covered": [...],
    "emergency_assembly_points": [...],
    "emergency_communication_methods": [...],
    "personal_emergency_evacuation_plans": {...},
    "emergency_access_requirements": {...},
    "emergency_equipment_locations": [...]
  }
}
```

## Confidence Scoring

Each extracted field should include a confidence score (0.0 to 1.0) based on:
- **Explicit mention**: 0.9-1.0 (field explicitly stated)
- **Strong inference**: 0.7-0.9 (clear context suggests value)
- **Weak inference**: 0.5-0.7 (some context but uncertain)
- **Not found**: null or 0.0

## Extraction Priority

1. **High Priority**: Compliance indicators, PAP information, evacuation strategies, fire safety measures
2. **Medium Priority**: MOR references, BSR interactions, maintenance requirements
3. **Lower Priority**: Engagement strategy details, accessibility measures, specific contact information
