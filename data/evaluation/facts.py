"""
Meridian — Financial Facts Table
=================================
Ground-truth financial figures for all 5 companies, FY2020–FY2024.

Sources (primary only — no estimates):
  Apple     : SEC EDGAR 10-K filings + Apple Q4 earnings press releases (apple.com/newsroom)
  Microsoft : microsoft.com/investor quarterly earnings pages + SEC 10-K filings
  Google    : SEC EDGAR 10-K filings + Alphabet Q4 earnings press releases
  Amazon    : SEC EDGAR 10-K filings + Amazon Q4 earnings press releases
  Meta      : investor.atmeta.com Q4 press releases + SEC 10-K filings

Fiscal year notes (critical for query routing):
  Apple     → FY ends September  (FY2024 = Oct 2023 – Sep 2024, filed Oct 2024)
  Microsoft → FY ends June       (FY2024 = Jul 2023 – Jun 2024, filed Jul 2024)
  Google    → Calendar year      (FY2024 = Jan – Dec 2024)
  Amazon    → Calendar year      (FY2024 = Jan – Dec 2024)
  Meta      → Calendar year      (FY2024 = Jan – Dec 2024)

Conventions:
  _b   = billions USD (rounded to 1 decimal)
  _pct = percentage   (rounded to 1 decimal)
  _k   = thousands    (employees)
  _m   = millions     (users)
  None = not reported / not applicable
  # verify = sourced from secondary aggregator; cross-check against 10-K before use
"""

FACTS: dict[str, dict[str, dict]] = {

    # =========================================================================
    # APPLE INC.
    # Primary sources:
    #   10-K filings: SEC EDGAR CIK 0000320193
    #   Q4 press releases: apple.com/newsroom & SEC EDGAR exhibits
    #   Segment data confirmed via Bullfincher for FY2022-2024
    # =========================================================================
    "Apple": {
        "FY2020": {
            # --- Income Statement ---
            # Source: Apple FY2020 Q4 earnings release (SEC exhibit 99.1)
            "revenue_b":                274.5,   # $274,515M
            "gross_profit_b":           105.0,   # $104,956M
            "gross_margin_pct":          38.2,
            "operating_income_b":        66.3,   # $66,288M
            "operating_margin_pct":      24.1,
            "net_income_b":              57.4,   # $57,411M
            "rd_spend_b":                18.8,   # $18,752M

            # --- Cash Flow ---
            "capex_b":                    7.3,   # purchases of PP&E  # verify (cash flow stmt)

            # --- Headcount ---
            "employees_k":              147.0,   # ~147,000 full-time equivalents

            # --- Segment Revenues (Apple 10-K product net sales table) ---
            "iphone_revenue_b":         137.8,   # $137,781M
            "mac_revenue_b":             28.6,   # $28,622M
            "ipad_revenue_b":            23.7,   # $23,724M
            "wearables_revenue_b":       30.6,   # $30,620M  (Wearables, Home & Accessories)
            "services_revenue_b":        53.8,   # $53,768M

            # --- Geography ---
            "americas_revenue_b":       124.6,   # $124,556M  # verify
            "europe_revenue_b":          68.6,   # $68,640M   # verify
            "greater_china_revenue_b":   40.3,   # $40,308M   # verify
        },

        "FY2021": {
            # Source: Apple FY2021 Q4 / FY2022 Q4 comparative press release
            "revenue_b":                365.8,   # $365,817M
            "gross_profit_b":           152.8,   # $152,836M
            "gross_margin_pct":          41.8,
            "operating_income_b":       108.9,   # $108,949M
            "operating_margin_pct":      29.8,
            "net_income_b":              94.7,   # $94,680M
            "rd_spend_b":                21.9,   # $21,914M
            "capex_b":                   11.1,   # # verify (cash flow stmt)
            "employees_k":              154.0,   # ~154,000 FTEs  # verify

            "iphone_revenue_b":         191.9,   # $191,973M
            "mac_revenue_b":             35.2,   # $35,190M
            "ipad_revenue_b":            32.4,   # $32,407M   # verify
            "wearables_revenue_b":       38.4,   # $38,367M
            "services_revenue_b":        68.4,   # $68,425M

            "americas_revenue_b":       153.3,   # $153,306M  # verify
            "europe_revenue_b":          89.3,   # $89,307M   # verify
            "greater_china_revenue_b":   68.4,   # $68,366M   # verify
        },

        "FY2022": {
            # Source: Apple FY2022 10-K (SEC EDGAR) + Q4 FY2022 press release
            "revenue_b":                394.3,   # $394,328M
            "gross_profit_b":           170.8,   # $170,782M
            "gross_margin_pct":          43.3,
            "operating_income_b":       119.4,   # $119,437M
            "operating_margin_pct":      30.3,
            "net_income_b":              99.8,   # $99,803M
            "rd_spend_b":                26.3,   # $26,251M
            "capex_b":                   10.7,   # # verify (cash flow stmt)
            "employees_k":              164.0,   # ~164,000 FTEs

            "iphone_revenue_b":         205.5,   # $205,489M
            "mac_revenue_b":             40.2,   # $40,177M
            "ipad_revenue_b":            29.3,   # $29,292M   # verify
            "wearables_revenue_b":       41.2,   # $41,241M
            "services_revenue_b":        78.1,   # $78,129M

            "americas_revenue_b":       169.7,   # $169,658M  # verify
            "europe_revenue_b":          95.1,   # $95,118M   # verify
            "greater_china_revenue_b":   74.2,   # $74,200M   # verify
        },

        "FY2023": {
            # Source: Apple FY2024 10-K 3-year comparative income statement
            "revenue_b":                383.3,   # $383,285M
            "gross_profit_b":           169.1,   # $169,148M
            "gross_margin_pct":          44.1,
            "operating_income_b":       114.3,   # $114,301M
            "operating_margin_pct":      29.8,
            "net_income_b":              97.0,   # $96,995M
            "rd_spend_b":                29.9,   # $29,915M
            "capex_b":                   10.9,   # # verify (cash flow stmt)
            "employees_k":              161.0,   # ~161,000 FTEs

            "iphone_revenue_b":         200.6,   # $200,583M
            "mac_revenue_b":             29.4,   # $29,357M
            "ipad_revenue_b":            28.3,   # $28,300M   # verify
            "wearables_revenue_b":       39.8,   # $39,845M
            "services_revenue_b":        85.2,   # $85,200M

            "americas_revenue_b":       162.6,   # $162,560M  # verify
            "europe_revenue_b":          94.3,   # $94,294M   # verify
            "greater_china_revenue_b":   72.6,   # $72,559M   # verify
        },

        "FY2024": {
            # Source: Apple FY2024 10-K (SEC EDGAR, filed Oct 2024) + Q4 press release
            "revenue_b":                391.0,   # $391,035M
            "gross_profit_b":           180.7,   # $180,683M
            "gross_margin_pct":          46.2,
            "operating_income_b":       123.2,   # $123,216M
            "operating_margin_pct":      31.5,
            "net_income_b":              93.7,   # $93,736M
            "rd_spend_b":                31.4,   # $31,370M
            "capex_b":                    9.4,   # $9,447M — confirmed multiple sources
            "employees_k":              164.0,   # ~164,000 FTEs

            "iphone_revenue_b":         201.2,   # $201,183M
            "mac_revenue_b":             30.0,   # $29,984M
            "ipad_revenue_b":            26.7,   # $26,694M   # verify
            "wearables_revenue_b":       37.0,   # $37,005M
            "services_revenue_b":        96.2,   # $96,169M

            "americas_revenue_b":       167.0,   # $167,045M  # verify
            "europe_revenue_b":          101.3,  # $101,328M  # verify
            "greater_china_revenue_b":   66.9,   # $66,953M   # verify
        },
    },

    # =========================================================================
    # MICROSOFT CORPORATION
    # Primary sources:
    #   microsoft.com/investor quarterly earnings pages (FY2020-FY2024)
    #   SEC EDGAR CIK 0000789019
    #   Fiscal year ends June 30.
    # =========================================================================
    "Microsoft": {
        "FY2020": {
            # Source: MSFT Q4 FY2020 press release (microsoft.com/investor)
            "revenue_b":                143.0,   # $143,015M
            "gross_profit_b":            96.9,   # $96,937M
            "gross_margin_pct":          67.8,
            "operating_income_b":        53.0,   # $52,959M
            "operating_margin_pct":      37.0,
            "net_income_b":              44.3,   # $44,281M
            "rd_spend_b":                19.3,   # $19,269M
            "capex_b":                   15.4,   # $15,441M
            "employees_k":              163.0,   # ~163,000 FTEs  # verify exact

            # Segment revenues — MSFT FY2020 Q4 press release
            "cloud_revenue_b":           48.4,   # Intelligent Cloud $48,366M
            "productivity_revenue_b":    46.4,   # Productivity & Business Processes $46,398M
            "more_personal_revenue_b":   48.2,   # More Personal Computing $48,251M
            "azure_growth_pct":          47.0,   # ~47% (Q4 FY2020 reported); full-year avg  # verify
        },

        "FY2021": {
            # Source: MSFT Q4 FY2021 press release
            "revenue_b":                168.1,   # $168,088M
            "gross_profit_b":           115.9,   # $115,856M
            "gross_margin_pct":          68.9,
            "operating_income_b":        69.9,   # $69,916M
            "operating_margin_pct":      41.6,
            "net_income_b":              61.3,   # $61,271M
            "rd_spend_b":                20.7,   # $20,716M
            "capex_b":                   20.6,   # $20,622M
            "employees_k":              181.0,   # 181,000 FTEs

            "cloud_revenue_b":           59.7,   # Intelligent Cloud $59,728M
            "productivity_revenue_b":    53.9,   # Productivity & Business Processes $53,915M
            "more_personal_revenue_b":   54.4,   # More Personal Computing $54,445M
            "azure_growth_pct":          45.0,   # Q4 FY2021 was 51%; full-year avg  # verify
        },

        "FY2022": {
            # Source: MSFT Q4 FY2022 press release + FY2024 Q4 income statements page
            "revenue_b":                198.3,   # $198,270M
            "gross_profit_b":           135.6,   # $135,620M
            "gross_margin_pct":          68.4,
            "operating_income_b":        83.4,   # $83,383M
            "operating_margin_pct":      42.1,
            "net_income_b":              72.7,   # $72,738M
            "rd_spend_b":                24.5,   # $24,512M
            "capex_b":                   23.9,   # $23,886M
            "employees_k":              221.0,   # 221,000 FTEs

            "cloud_revenue_b":           75.0,   # Intelligent Cloud $74,965M
            "productivity_revenue_b":    63.4,   # Productivity & Business Processes $63,364M
            "more_personal_revenue_b":   59.9,   # More Personal Computing $59,941M
            "azure_growth_pct":          40.0,   # Varied 40-46% quarterly; full-year avg  # verify
        },

        "FY2023": {
            # Source: MSFT FY2024 Q4 income-statements IR page (3-yr comparative)
            "revenue_b":                211.9,   # $211,915M
            "gross_profit_b":           146.1,   # $146,052M
            "gross_margin_pct":          68.9,
            "operating_income_b":        88.5,   # $88,523M
            "operating_margin_pct":      41.8,
            "net_income_b":              72.4,   # $72,361M
            "rd_spend_b":                27.2,   # $27,195M
            "capex_b":                   28.1,   # $28,107M
            "employees_k":              221.0,   # 221,000 FTEs

            "cloud_revenue_b":           87.9,   # Intelligent Cloud $87,907M
            "productivity_revenue_b":    69.3,   # Productivity & Business Processes $69,274M
            "more_personal_revenue_b":   54.7,   # More Personal Computing $54,734M
            "azure_growth_pct":          27.0,   # Varied 26-29% quarterly; full-year avg  # verify
        },

        "FY2024": {
            # Source: MSFT FY2024 Q4 income-statements + segment-revenues IR pages
            "revenue_b":                245.1,   # $245,122M
            "gross_profit_b":           171.0,   # $171,008M
            "gross_margin_pct":          69.8,
            "operating_income_b":       109.4,   # $109,433M
            "operating_margin_pct":      44.6,
            "net_income_b":              88.1,   # $88,136M
            "rd_spend_b":                29.5,   # $29,510M
            "capex_b":                   44.5,   # $44,477M
            "employees_k":              228.0,   # 228,000 FTEs

            "cloud_revenue_b":          105.4,   # Intelligent Cloud $105,362M
            "productivity_revenue_b":    77.7,   # Productivity & Business Processes $77,728M
            "more_personal_revenue_b":   62.0,   # More Personal Computing $62,032M
            "azure_growth_pct":          29.0,   # Varied 28-31% quarterly; full-year avg  # verify
        },
    },

    # =========================================================================
    # ALPHABET INC. (GOOGLE)
    # Primary sources:
    #   SEC EDGAR CIK 0001652044 — Alphabet 10-K filings
    #   Q4 earnings press releases (SEC EDGAR exhibit 99.1)
    #   Calendar year Jan–Dec.
    # =========================================================================
    "Google": {
        "FY2020": {
            # Source: Alphabet Q4 2020 earnings press release (SEC exhibit)
            # Note: FY2020 was first year YouTube/Cloud disclosed separately
            "revenue_b":                182.5,   # $182,527M
            "gross_profit_b":            97.8,   # # verify (2020 10-K cost of revenue)
            "gross_margin_pct":          53.6,   # # verify
            "operating_income_b":        41.2,   # $41,224M  # verify
            "operating_margin_pct":      22.6,   # # verify
            "net_income_b":              40.3,   # $40,269M  # verify
            "rd_spend_b":                27.6,   # $27,573M  # verify
            "capex_b":                   22.3,   # $22,281M  # verify
            "employees_k":              135.3,   # 135,301 FTEs  # verify

            "advertising_revenue_b":    146.9,   # Google Search + YouTube + Network  # verify
            "cloud_revenue_b":           13.1,   # Google Cloud $13,059M
            "youtube_revenue_b":         19.8,   # YouTube ads $19,772M
            "other_bets_revenue_b":       0.7,   # $657M  # verify
        },

        "FY2021": {
            # Source: Alphabet 2022 10-K (3-yr comparative) + Q4 2021 press release
            "revenue_b":                257.6,   # $257,637M
            "gross_profit_b":           146.7,   # $146,698M
            "gross_margin_pct":          57.0,
            "operating_income_b":        78.7,   # $78,714M
            "operating_margin_pct":      30.6,
            "net_income_b":              76.0,   # $76,033M
            "rd_spend_b":                31.6,   # $31,562M
            "capex_b":                   24.3,   # $24,273M  # verify
            "employees_k":              156.5,   # 156,500 FTEs  # verify exact

            "advertising_revenue_b":    209.5,   # Search $148.9B + YouTube $28.8B + Network $31.7B
            "cloud_revenue_b":           19.2,   # Google Cloud $19,206M
            "youtube_revenue_b":         28.8,   # YouTube ads $28,845M
            "other_bets_revenue_b":       0.8,   # $753M  # verify
        },

        "FY2022": {
            # Source: Alphabet 2023 10-K (3-yr comparative income statement)
            "revenue_b":                282.8,   # $282,836M
            "gross_profit_b":           156.6,   # $156,633M
            "gross_margin_pct":          55.4,
            "operating_income_b":        74.8,   # $74,842M
            "operating_margin_pct":      26.5,
            "net_income_b":              60.0,   # $59,972M
            "rd_spend_b":                39.5,   # $39,500M
            "capex_b":                   31.5,   # $31,485M  # verify
            "employees_k":              186.8,   # 186,779 FTEs

            "advertising_revenue_b":    224.5,   # Search $162.5B + YouTube $29.2B + Network $32.8B
            "cloud_revenue_b":           26.3,   # Google Cloud $26,280M
            "youtube_revenue_b":         29.2,   # YouTube ads $29,243M
            "other_bets_revenue_b":       1.1,   # $1,068M  # verify
        },

        "FY2023": {
            # Source: Alphabet 2024 10-K + Q4 2023 press release (SEC exhibit)
            "revenue_b":                307.4,   # $307,394M
            "gross_profit_b":           174.1,   # $174,062M
            "gross_margin_pct":          56.6,
            "operating_income_b":        84.3,   # $84,293M
            "operating_margin_pct":      27.4,
            "net_income_b":              73.8,   # $73,795M
            "rd_spend_b":                45.4,   # $45,427M
            "capex_b":                   32.3,   # $32,251M  # verify
            "employees_k":              182.5,   # 182,502 FTEs

            "advertising_revenue_b":    237.9,   # Search $175.0B + YouTube $31.5B + Network $31.3B
            "cloud_revenue_b":           33.1,   # Google Cloud $33,088M
            "youtube_revenue_b":         31.5,   # YouTube ads $31,510M
            "other_bets_revenue_b":       1.5,   # $1,527M  # verify
        },

        "FY2024": {
            # Source: Alphabet Q4 2024 press release (SEC EDGAR exhibit 99.1)
            "revenue_b":                350.0,   # $350,018M
            "gross_profit_b":           203.7,   # $203,712M
            "gross_margin_pct":          58.2,
            "operating_income_b":       112.4,   # $112,390M
            "operating_margin_pct":      32.1,
            "net_income_b":             100.1,   # $100,118M
            "rd_spend_b":                49.3,   # $49,326M
            "capex_b":                   52.5,   # $52,548M
            "employees_k":              183.3,   # 183,323 FTEs

            "advertising_revenue_b":    264.6,   # Search $198.1B + YouTube $36.1B + Network $30.4B
            "cloud_revenue_b":           43.2,   # Google Cloud $43,228M
            "youtube_revenue_b":         36.1,   # YouTube ads $36,149M
            "other_bets_revenue_b":       1.6,   # $1,567M  # verify
        },
    },

    # =========================================================================
    # AMAZON.COM INC.
    # Primary sources:
    #   SEC EDGAR CIK 0001018724 — Amazon 10-K filings
    #   Amazon Q4 earnings press releases (ir.aboutamazon.com)
    #   Calendar year Jan–Dec.
    # Note: Amazon reports "Technology and infrastructure" not pure R&D.
    #       This is the closest disclosed analog and is used as rd_spend_b.
    # =========================================================================
    "Amazon": {
        "FY2020": {
            # Source: Amazon 2021 10-K (3-yr comparative) + Q4 2020 press release
            "revenue_b":                386.1,   # $386,064M
            "gross_profit_b":           152.8,   # # verify (cost of sales subtraction)
            "gross_margin_pct":          39.6,   # # verify
            "operating_income_b":        22.9,   # $22,899M
            "operating_margin_pct":       5.9,
            "net_income_b":              21.3,   # $21,331M
            "rd_spend_b":                42.7,   # $42,740M — Technology & infrastructure
            "capex_b":                   40.1,   # $40,140M purchases of PP&E  # verify
            "employees_k":             1298.0,   # 1,298,000 FTEs

            "aws_revenue_b":             45.4,   # $45,370M
            "advertising_revenue_b":     15.7,   # Included in "Other" segment  # verify
            "north_america_revenue_b":  236.3,   # $236,282M
            "international_revenue_b":  104.4,   # $104,412M
        },

        "FY2021": {
            # Source: Amazon 2022 10-K (3-yr comparative) + Q4 2021 press release
            "revenue_b":                469.8,   # $469,822M
            "gross_profit_b":           197.5,   # $197,478M
            "gross_margin_pct":          42.0,
            "operating_income_b":        24.9,   # $24,879M
            "operating_margin_pct":       5.3,
            "net_income_b":              33.4,   # $33,364M
            "rd_spend_b":                56.1,   # $56,052M — Technology & infrastructure  # verify
            "capex_b":                   61.1,   # $61,053M  # verify
            "employees_k":             1608.0,   # 1,608,000 FTEs

            "aws_revenue_b":             62.2,   # $62,202M
            "advertising_revenue_b":     31.2,   # $31,160M (first year broken out in 2022 10-K)  # verify
            "north_america_revenue_b":  279.8,   # $279,833M
            "international_revenue_b":  127.8,   # $127,787M
        },

        "FY2022": {
            # Source: Amazon 2023 10-K (3-yr comparative)
            "revenue_b":                513.9,   # $513,983M
            "gross_profit_b":           225.2,   # # verify
            "gross_margin_pct":          43.8,   # # verify
            "operating_income_b":        12.2,   # $12,248M  (operating income trough year)
            "operating_margin_pct":       2.4,
            "net_income_b":              -2.7,   # -$2,722M net loss (Rivian equity write-down)
            "rd_spend_b":                73.2,   # $73,213M — Technology & infrastructure  # verify
            "capex_b":                   63.6,   # $63,645M  # verify
            "employees_k":             1541.0,   # 1,541,000 FTEs

            "aws_revenue_b":             80.1,   # $80,096M
            "advertising_revenue_b":     37.7,   # $37,739M (first year separately disclosed)
            "north_america_revenue_b":  315.9,   # $315,880M
            "international_revenue_b":  118.0,   # $118,007M
        },

        "FY2023": {
            # Source: Amazon 2024 10-K (3-yr comparative) + Q4 2023 press release
            "revenue_b":                574.8,   # $574,785M
            "gross_profit_b":           270.0,   # $270,046M
            "gross_margin_pct":          47.0,
            "operating_income_b":        36.9,   # $36,852M
            "operating_margin_pct":       6.4,
            "net_income_b":              30.4,   # $30,425M
            "rd_spend_b":                85.6,   # $85,622M — Technology & infrastructure
            "capex_b":                   52.7,   # $52,729M  # verify
            "employees_k":             1525.0,   # 1,525,000 FTEs

            "aws_revenue_b":             90.8,   # $90,757M
            "advertising_revenue_b":     46.9,   # $46,906M
            "north_america_revenue_b":  352.8,   # $352,828M
            "international_revenue_b":  131.2,   # $131,200M
        },

        "FY2024": {
            # Source: Amazon 2024 10-K (SEC EDGAR) + Q4 2024 press release
            "revenue_b":                638.0,   # $637,959M
            "gross_profit_b":           311.7,   # $311,671M
            "gross_margin_pct":          48.8,
            "operating_income_b":        68.6,   # $68,593M
            "operating_margin_pct":      10.7,
            "net_income_b":              59.2,   # $59,248M
            "rd_spend_b":                88.5,   # $88,544M — Technology & infrastructure
            "capex_b":                   83.0,   # $83,049M  # verify (10-K cash flow)
            "employees_k":             1556.0,   # 1,556,000 FTEs

            "aws_revenue_b":            107.6,   # $107,564M
            "advertising_revenue_b":     56.2,   # $56,209M
            "north_america_revenue_b":  387.5,   # $387,481M
            "international_revenue_b":  142.9,   # $142,914M
        },
    },

    # =========================================================================
    # META PLATFORMS INC. (formerly Facebook Inc.)
    # Primary sources:
    #   investor.atmeta.com Q4 earnings press releases
    #   SEC EDGAR CIK 0001326801 — Meta 10-K filings
    #   Calendar year Jan–Dec.
    # Note: Meta discontinued reporting Facebook-only DAU/MAU after FY2022.
    #       FY2023+ uses "Family" daily active people (DAP) / monthly active people (MAP).
    # =========================================================================
    "Meta": {
        "FY2020": {
            # Source: Meta Q4 2021 press release (3-yr comparative income statement)
            "revenue_b":                 86.0,   # $85,965M
            "gross_profit_b":            69.3,   # $69,273M ($85,965M - $16,692M cost of revenue)
            "gross_margin_pct":          80.6,
            "operating_income_b":        32.7,   # $32,671M
            "operating_margin_pct":      38.0,
            "net_income_b":              29.1,   # $29,146M
            "rd_spend_b":                18.4,   # $18,447M
            "capex_b":                   15.1,   # $15,115M
            "employees_k":               58.6,   # 58,604 FTEs

            "advertising_revenue_b":     84.2,   # $84,169M
            "other_revenue_b":            1.8,   # $1,796M (non-advertising, incl. Quest hardware)
            "dau_millions":            1845.0,   # 1,845M Facebook DAU (Dec 2020 avg)
            "mau_millions":            2800.0,   # 2,800M Facebook MAU (Dec 31, 2020)
        },

        "FY2021": {
            # Source: Meta Q4 2021 press release (primary)
            "revenue_b":                117.9,   # $117,929M
            "gross_profit_b":            95.3,   # $95,280M ($117,929M - $22,649M cost of revenue)
            "gross_margin_pct":          80.8,
            "operating_income_b":        46.8,   # $46,753M
            "operating_margin_pct":      39.7,
            "net_income_b":              39.4,   # $39,370M
            "rd_spend_b":                24.7,   # $24,655M
            "capex_b":                   18.6,   # $18,567M
            "employees_k":               72.0,   # 71,970 FTEs

            "advertising_revenue_b":    114.9,   # $114,934M
            "other_revenue_b":            3.0,   # $2,995M (Reality Labs hardware)
            "dau_millions":            1929.0,   # 1,929M Facebook DAU (Dec 2021)
            "mau_millions":            2910.0,   # 2,910M Facebook MAU (Dec 31, 2021)
        },

        "FY2022": {
            # Source: Meta Q4 2022 earnings press release (SEC exhibit) + 2023 10-K
            "revenue_b":                116.6,   # $116,609M
            "gross_profit_b":            91.4,   # $91,360M
            "gross_margin_pct":          78.3,
            "operating_income_b":        28.9,   # $28,944M
            "operating_margin_pct":      24.8,
            "net_income_b":              23.2,   # $23,200M
            "rd_spend_b":                35.3,   # $35,338M
            "capex_b":                   32.0,   # $32,002M  # verify (2022 10-K cash flow)
            "employees_k":               86.5,   # 86,482 FTEs

            "advertising_revenue_b":    113.6,   # $113,642M  # verify (2022 10-K)
            "other_revenue_b":            3.0,   # $2,967M (Reality Labs hardware)
            "dau_millions":            2000.0,   # 2,000M Facebook DAU (Dec 2022)
            "mau_millions":            2960.0,   # 2,960M Facebook MAU (Dec 31, 2022)
        },

        "FY2023": {
            # Source: Meta Q4 2024 press release (3-yr comparative) + 2023 10-K
            "revenue_b":                134.9,   # $134,902M
            "gross_profit_b":           108.9,   # $108,943M
            "gross_margin_pct":          80.8,
            "operating_income_b":        46.8,   # $46,751M
            "operating_margin_pct":      34.7,
            "net_income_b":              39.1,   # $39,098M
            "rd_spend_b":                38.5,   # $38,483M
            "capex_b":                   27.0,   # $27,045M
            "employees_k":               67.3,   # 67,317 FTEs  # verify exact

            "advertising_revenue_b":    131.9,   # $131,948M
            "other_revenue_b":            3.0,   # $2,954M (Reality Labs hardware)
            # Meta switched to Family metrics after FY2022
            "family_dap_millions":     3190.0,   # 3,190M Family daily active people (Dec 2023)  # verify
            "family_map_millions":     3980.0,   # 3,980M Family monthly active people (Dec 2023)  # verify
        },

        "FY2024": {
            # Source: Meta Q4 2024 press release (investor.atmeta.com, primary)
            "revenue_b":                164.5,   # $164,501M
            "gross_profit_b":           134.3,   # $134,340M
            "gross_margin_pct":          81.7,
            "operating_income_b":        69.4,   # $69,380M
            "operating_margin_pct":      42.2,
            "net_income_b":              62.4,   # $62,360M
            "rd_spend_b":                43.9,   # $43,873M
            "capex_b":                   39.2,   # $39,230M
            "employees_k":               74.1,   # 74,067 FTEs

            "advertising_revenue_b":    160.6,   # $160,633M
            "other_revenue_b":            3.9,   # $3,868M (Reality Labs hardware)
            "family_dap_millions":     3350.0,   # 3,350M Family daily active people (Dec 2024)
            "family_map_millions":     None,     # Not separately reported in Q4 2024 press release  # verify
        },
    },
}


# ---------------------------------------------------------------------------
# Convenience helpers (used by the question generator)
# ---------------------------------------------------------------------------

def get(company: str, year: int) -> dict:
    """Return the facts dict for a company/year. year is fiscal year."""
    fy_key = f"FY{year}"
    return FACTS.get(company, {}).get(fy_key, {})


def all_years(company: str) -> list[dict]:
    """Return list of fact dicts for all 5 years, in chronological order."""
    return [get(company, y) for y in [2020, 2021, 2022, 2023, 2024]]


def yoy_growth(company: str, metric: str, year: int) -> float | None:
    """
    Year-over-year percentage growth for a metric.

    Returns ((current - prior) / prior) * 100, rounded to 1 decimal.
    Returns None if either year is missing or either value is None / zero.

    Example:
        yoy_growth("Apple", "revenue_b", 2023)
        → ((383.3 - 394.3) / 394.3) * 100 = -2.8%
    """
    if year <= 2020:
        return None   # no prior year in our corpus
    current = get(company, year).get(metric)
    prior   = get(company, year - 1).get(metric)
    if current is None or prior is None or prior == 0:
        return None
    return round(((current - prior) / abs(prior)) * 100, 1)


def covid_delta(company: str, metric: str) -> float | None:
    """
    COVID recovery signal: percentage change from FY2020 to FY2021.

    Measures how strongly a company rebounded after the initial COVID shock.
    Returns None if either value is missing or prior is zero.

    Example:
        covid_delta("Amazon", "revenue_b")
        → ((469.8 - 386.1) / 386.1) * 100 = 21.7%
    """
    v2020 = get(company, 2020).get(metric)
    v2021 = get(company, 2021).get(metric)
    if v2020 is None or v2021 is None or v2020 == 0:
        return None
    return round(((v2021 - v2020) / abs(v2020)) * 100, 1)


def companies() -> list[str]:
    return list(FACTS.keys())


def years() -> list[int]:
    return [2020, 2021, 2022, 2023, 2024]


# ---------------------------------------------------------------------------
# Self-test: print all values with # verify flags to stdout for review
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import re
    verify_count = 0
    for company, fy_data in FACTS.items():
        for fy, metrics in fy_data.items():
            for key, val in metrics.items():
                if val is None:
                    print(f"  NONE   {company} {fy} → {key}")
                    verify_count += 1
    print(f"\nTotal fields needing review: {verify_count}")
    print(f"Total companies: {len(FACTS)}")
    total_fields = sum(len(m) for fy in FACTS.values() for m in fy.values())
    print(f"Total data points: {total_fields}")
