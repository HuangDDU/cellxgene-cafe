

_EXPLORER_BENCHMARK_METRICS = [
    "pseudotime_correlation",
    "isomorphic",
    "edge_flip",
    "him",
    "correlation",
    "F1_branches",
    "F1_milestones",
    "time",
    "memory",
]

_EXPLORER_GENE_SETS = [
    {
        "name": "T cell differentiation",
        "category": "immune",
        "genes": ["CD3D", "CD3E", "CD4", "CD8A", "IL7R", "CCR7", "TCF7", "GATA3", "TBX21", "FOXP3"],
    },
    {
        "name": "Cytotoxic lymphocyte program",
        "category": "immune",
        "genes": ["NKG7", "GNLY", "GZMB", "GZMA", "PRF1", "IFNG", "KLRD1", "KLRB1"],
    },
    {
        "name": "Interferon response",
        "category": "pathway",
        "genes": ["ISG15", "IFIT1", "IFIT2", "IFIT3", "MX1", "OAS1", "STAT1", "IRF7", "IFI6", "CXCL10"],
    },
    {
        "name": "Cell cycle G2M",
        "category": "pathway",
        "genes": ["MKI67", "TOP2A", "CENPF", "NUSAP1", "UBE2C", "CCNB1", "BIRC5", "CDK1", "AURKB"],
    },
    {
        "name": "Epithelial identity",
        "category": "lineage",
        "genes": ["EPCAM", "KRT8", "KRT18", "KRT19", "MUC1", "CLDN4", "CDH1"],
    },
    {
        "name": "EMT and migration",
        "category": "pathway",
        "genes": ["VIM", "FN1", "SNAI1", "SNAI2", "ZEB1", "ZEB2", "TWIST1", "ITGA5", "COL1A1"],
    },
    {
        "name": "Hypoxia response",
        "category": "pathway",
        "genes": ["HIF1A", "VEGFA", "CA9", "LDHA", "SLC2A1", "ENO1", "PGK1", "BNIP3"],
    },
    {
        "name": "Apoptosis",
        "category": "pathway",
        "genes": ["BAX", "BAK1", "CASP3", "CASP8", "CASP9", "FAS", "BCL2", "BID", "PMAIP1"],
    },
    {
        "name": "Myeloid activation",
        "category": "immune",
        "genes": ["LYZ", "S100A8", "S100A9", "FCGR3A", "LST1", "CTSS", "TYROBP", "AIF1", "CST3"],
    },
]
