// Mock property data for the EquiRisk dashboard

export const RAW_PROPERTIES = [
    {
      id: 1,
      clientName: "Example Housing Association",
      policyReference: "EX-2024-0001",
      productType: "Social Housing Property",
      propertyReference: "EXA1",
      blockReference: "Block 1",
      occupancyType: "Rented",
  
      deductible: 2500,
      floodDeductible: 5000,
      stormDeductible: 2500,
      deductibleBasis: "Each and every loss",
  
      address1: "12 Caledonia Street",
      address2: "",
      address3: "",
      postcode: "EH7 5QX",
      city: "Edinburgh",
      region: "Scotland",
  
      numberOfUnits: 8,
      sumInsured: 1200000,
      sumInsuredType: "Reinstatement",
  
      avidPropertyType: "Traditional Tenement",
      propertyType: "Tenement Flat",
      wallConstruction: "Solid masonry",
      roofConstruction: "Pitched slate",
      floorConstruction: "Timber",
      yearBuilt: 1935,
      ageBanding: "1901–1919",
      numberOfBedrooms: 2,
      numberOfStoreys: 4,
      basementLocation: "None",
      listedBuilding: "Not listed",
  
      securityFeatures: "Secure entry, intercom",
      fireProtection: "Mains-wired detectors, compartmentation",
      alarms: "LD2 fire alarm",
  
      floodInsured: true,
      stormInsured: true,
  
      epcRating: "D",
      deprivationIndex: 8.2,
      floodScore: 0.7,
      crimeIndex: 6.1,
      lastClaimDate: "2023-11-02",
      claimFrequency: 0.18,
      expectedSeverity: 2200,
      purePremium: 396,
      maintenanceScore: 6.5,
      voidDaysLastYear: 12,
      riskBand: "High",
  
      lat: 55.957,
      lon: -3.177,
  
      docBRef: "2023CP123456 Block A",
      singleLocationOrPortfolio: "Part of portfolio",
      floorsAboveGround: 4,
      floorsBelowGround: 0,
      claddingType: "Masonry with limited ACM panels",
      ewsStatus: "EWS1 Form B1",
      fireRiskManagementSummary: "FRAs annually, weekly alarm tests",
      evacuationStrategy: "Stay put with PEEPs for vulnerable tenants",
    },
  
    {
      id: 2,
      clientName: "Example Housing Association",
      policyReference: "EX-2024-0001",
      productType: "Social Housing Property",
      propertyReference: "EXA2",
      blockReference: "Block 1",
      occupancyType: "Rented",
  
      deductible: 2500,
      floodDeductible: 2500,
      stormDeductible: 2500,
  
      address1: "5 Meadow Close",
      postcode: "EH11 3PL",
      city: "Edinburgh",
  
      numberOfUnits: 6,
      sumInsured: 900000,
  
      avidPropertyType: "Modern terraced",
      propertyType: "Terraced House",
      wallConstruction: "Brick cavity",
      roofConstruction: "Tiled pitched",
  
      epcRating: "B",
      deprivationIndex: 3.2,
      floodScore: 0.15,
      crimeIndex: 4.0,
      claimFrequency: 0.05,
      maintenanceScore: 8.1,
      voidDaysLastYear: 3,
      riskBand: "Low",
  
      lat: 55.935,
      lon: -3.244,
    },
  
    {
      id: 3,
      address1: "27 Riverside Court",
      postcode: "G5 9AB",
      city: "Glasgow",
  
      numberOfUnits: 30,
      sumInsured: 5140000,
  
      propertyType: "High-Rise Flat",
      wallConstruction: "Reinforced concrete with cladding",
      roofConstruction: "Flat roof",
      numberOfStoreys: 12,
  
      epcRating: "C",
      floodScore: 0.55,
      crimeIndex: 7.8,
      claimFrequency: 0.25,
      maintenanceScore: 5.2,
      riskBand: "Very High",
  
      lat: 55.847,
      lon: -4.259,
  
      docBRef: "2023CP123456 Block B",
      claddingType: "Mixed ACM / brick",
      ewsStatus: "EWS1 Form B2 – remediation in progress",
      evacuationStrategy: "Simultaneous evacuation",
    },
  
    {
      id: 4,
      address1: "3 Bramble Grove",
      postcode: "NE4 7RT",
      city: "Newcastle",
  
      numberOfUnits: 10,
      sumInsured: 1585000,
  
      propertyType: "Semi-Detached",
      wallConstruction: "Brick cavity",
      roofConstruction: "Pitched tile",
  
      floodScore: 0.25,
      crimeIndex: 5.1,
      claimFrequency: 0.12,
      maintenanceScore: 7.3,
      riskBand: "Medium",
  
      lat: 54.974,
      lon: -1.632,
    },
  
    {
      id: 5,
      address1: "73 Eastgate Tower",
      postcode: "E1 3QA",
      city: "London",
  
      numberOfUnits: 120,
      sumInsured: 30000000,
  
      propertyType: "High-Rise Flat",
      wallConstruction: "Concrete frame with rainscreen cladding",
      roofConstruction: "Flat roof",
  
      floodScore: 0.25,
      crimeIndex: 9.1,
      claimFrequency: 0.29,
      maintenanceScore: 5.0,
      riskBand: "Very High",
  
      lat: 51.514,
      lon: -0.055,
  
      docBRef: "2023CP123456 Block C",
      claddingType: "Mixed metal / HPL panels",
      ewsStatus: "Intrusive survey completed – remediation planned",
      evacuationStrategy: "Phased evacuation",
    },
  ];