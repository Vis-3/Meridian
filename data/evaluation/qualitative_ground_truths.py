"""
Meridian — Qualitative Ground Truths (Risk Factors & MD&A)
============================================================
50 placeholder entries for risk_qualitative questions, one per company per topic.

Structure:
  id                        Q{template}_{Company}_{Year}
  type                      "risk_qualitative"
  question                  verbatim question text (matches questions.json)
  companies                 [company]
  years                     [fiscal_year]
  section                   primary 10-K section to retrieve from
  covid_related             True if pandemic context is central to the question
  keywords                  5-8 terms that correctly-retrieved chunks MUST contain
                            (used by retrieval evaluator as lightweight precision check)
  ground_truth_placeholder  search instructions for human annotator post-extraction
  ground_truth              None — filled after SEC filing extraction is complete

Topics:
  Q1   Supply chain risks               (5 entries: all companies, 2020-2022)
  Q2   Competitive landscape            (5 entries: all companies, 2022-2024)
  Q3   Macroeconomic risks              (5 entries: all companies, 2022-2023)
  Q4   New/escalated risks FY2020       (5 entries: all companies, covid_related=True)
  Q5   AI and ML investments            (5 entries: all companies, 2023-2024)
  Q6   Revenue outlook and guidance     (5 entries: all companies, 2022-2023)
  Q7   Regulatory and antitrust risks   (5 entries: Apple+Microsoft+Google+Amazon+Meta)
  Q8   Workforce strategy               (5 entries: all companies, 2022-2023)
  Q9   Cybersecurity risks              (5 entries: all companies, 2023-2024)
  Q10  Climate and ESG risks            (5 entries: all companies, 2023-2024)
"""

QUALITATIVE_GROUND_TRUTHS: list[dict] = [

    # =========================================================================
    # Q1 — Supply Chain Risks  (covid_related=True for 2020-2021 entries)
    # =========================================================================

    {
        "id":       "Q1_Apple_2021",
        "type":     "risk_qualitative",
        "question": "What supply chain risks did Apple identify in its FY2021 10-K, "
                    "and how exposed was the company to single-source suppliers?",
        "companies": ["Apple"],
        "years":    [2021],
        "section":  "Item 1A",
        "covid_related": True,
        "keywords": [
            "supply chain", "component shortage", "single-source", "sole-source",
            "Asia-Pacific", "Taiwan", "semiconductor", "manufacturing concentration",
        ],
        "ground_truth_placeholder": (
            "Look for: semiconductor component shortages linked to COVID-19 demand surge, "
            "explicit single-source or sole-source supplier language for key components, "
            "geographic concentration risk in Asia-Pacific manufacturing (Taiwan, China, "
            "Vietnam), logistics disruption language, and any new supply chain "
            "diversification language not present in FY2020 filing. Note whether Apple "
            "quantified the financial impact or kept language qualitative."
        ),
        "ground_truth": (
            "In its FY2021 10-K, Apple disclosed that its products often utilize custom components available from only one source, and that when a component or product uses new technologies, initial capacity constraints may exist until suppliers' yields have matured or their manufacturing capacities have increased. The company noted that it relies on single-source outsourcing partners in the U.S., Asia and Europe to supply and manufacture many components, and on outsourcing partners primarily located in Asia for final assembly of substantially all hardware products. Apple stated that any failure of these partners to perform can have a negative impact on the company's cost or supply of components or finished goods, and that manufacturing or logistics in these locations or transit to final destinations can be disrupted for a variety of reasons, including natural and man-made disasters, information technology system failures, commercial disputes, military actions, and public health issues. The company further noted it remains subject to significant risks of supply shortages and price increases that can materially adversely affect its business, results of operations and financial condition."
        ),
    },

    {
        "id":       "Q1_Microsoft_2022",
        "type":     "risk_qualitative",
        "question": "What supply chain risks did Microsoft describe in its FY2022 10-K, "
                    "and how did hardware component availability affect its devices business?",
        "companies": ["Microsoft"],
        "years":    [2022],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "supply chain", "component availability", "hardware", "Surface", "Xbox",
            "semiconductor", "manufacturing disruption", "third-party",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A risk language around hardware component availability for "
            "Surface and Xbox product lines, semiconductor shortage impacts on More Personal "
            "Computing segment, reliance on third-party hardware manufacturers (notably "
            "in China), and any discussion of geopolitical risk affecting hardware procurement. "
            "Compare language intensity vs FY2021 — supply chain pressure peaked mid-cycle. "
            "Check whether Microsoft explicitly mentioned Activision supply chain or kept "
            "to existing hardware businesses."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Microsoft disclosed that there are limited suppliers for certain device and datacenter components, and that competitors use some of the same suppliers, meaning their demand for hardware components can affect the capacity available to Microsoft. The company noted that if components are delayed or become unavailable, whether because of supplier capacity constraint, industry shortages, legal or regulatory changes that restrict supply sources, or other reasons, it may not obtain timely replacement supplies, resulting in reduced sales or inadequate datacenter capacity. Microsoft further stated that component shortages, excess or obsolete inventory, or price reductions resulting in inventory adjustments may adversely impact its financial results, including for its Surface and Xbox device product lines."
        ),
    },

    {
        "id":       "Q1_Google_2021",
        "type":     "risk_qualitative",
        "question": "What supply chain risks did Alphabet flag in its FY2021 10-K related "
                    "to data center infrastructure and hardware procurement?",
        "companies": ["Google"],
        "years":    [2021],
        "section":  "Item 1A",
        "covid_related": True,
        "keywords": [
            "supply chain", "data center", "hardware", "servers", "component",
            "semiconductor", "capacity", "infrastructure", "procurement",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A discussion of data center hardware procurement constraints "
            "during the COVID-era chip shortage, reliance on third-party suppliers for "
            "servers and networking equipment, geographic risk in hardware manufacturing, "
            "and any language about Google's custom silicon (TPUs) as a mitigation. "
            "Note whether Alphabet disclosed a specific dollar impact or kept language "
            "general. Compare against FY2020 to identify new supply chain language added "
            "in response to the shortage environment."
        ),
        "ground_truth": (
            "In its FY2021 10-K, Alphabet disclosed that it faces a number of manufacturing and supply chain risks that could harm its financial condition, operating results, and prospects. The company noted that it relies on other companies to manufacture many of its finished products, to design certain components and parts, and to participate in the distribution of its products and services, as well as to design, manufacture, or assemble certain components and parts in its technical infrastructure. Alphabet stated that it has experienced and may in the future experience supply shortages and/or price increases driven by raw material, component or part availability, manufacturing capacity, labor shortages, industry allocations, logistics capacity, tariffs, trade disputes, natural disasters or pandemics, and the effects of climate change. The company noted that its business could be negatively affected if it is not able to engage manufacturers with necessary capabilities on reasonable terms, or if those it engages fail to meet their obligations due to financial difficulties or other reasons."
        ),
    },

    {
        "id":       "Q1_Amazon_2021",
        "type":     "risk_qualitative",
        "question": "What supply chain and logistics risks did Amazon identify in its "
                    "FY2021 10-K, and how did fulfillment capacity constraints factor in?",
        "companies": ["Amazon"],
        "years":    [2021],
        "section":  "Item 1A",
        "covid_related": True,
        "keywords": [
            "supply chain", "fulfillment", "logistics", "inventory", "shipping",
            "third-party sellers", "delivery capacity", "carrier", "port congestion",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A risk language around fulfillment network capacity constraints "
            "during the COVID demand surge, reliance on third-party carriers (UPS, FedEx, USPS) "
            "alongside Amazon Logistics growth, port congestion and import inventory risk for "
            "third-party marketplace sellers, and language about product availability driving "
            "customer satisfaction. Note any language about AWS hardware supply constraints "
            "separately from e-commerce logistics. Check whether Amazon quantified fulfillment "
            "cost overruns as a supply chain risk item."
        ),
        "ground_truth": (
            "In its FY2021 10-K, Amazon disclosed that as its fulfillment and data center networks become increasingly complex, operating them becomes more challenging, with no assurance the company will be able to operate its networks effectively. The company noted that productivity across its fulfillment network was being affected by global supply chain constraints and constrained labor markets, which increase payroll costs and make it difficult to hire, train, and deploy a sufficient number of people to operate its fulfillment network as efficiently as desired. Amazon further disclosed that failure to optimize inventory or staffing in its fulfillment network increases net shipping cost by requiring long-zone or partial shipments, and that the company and its co-sourcers may be unable to adequately staff fulfillment centers and customer service centers during periods of high demand."
        ),
    },

    {
        "id":       "Q1_Meta_2022",
        "type":     "risk_qualitative",
        "question": "What supply chain risks did Meta highlight in its FY2022 10-K, "
                    "particularly regarding hardware for its Reality Labs (VR/AR) products?",
        "companies": ["Meta"],
        "years":    [2022],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "supply chain", "hardware", "Reality Labs", "Quest", "VR", "component",
            "manufacturing", "semiconductor", "third-party manufacturer", "inventory",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A risk language about component availability for Quest headsets "
            "and other Reality Labs hardware, single-source dependencies for display panels "
            "or specialized VR components, manufacturing concentration risk (likely China/Asia), "
            "inventory write-down risk if consumer demand for VR hardware disappoints, and "
            "any language about the challenge of hardware supply chain management given Meta's "
            "relatively new role as a hardware OEM. Note contrast with Meta's core ad business "
            "which is software-driven and lacks supply chain risk."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Meta disclosed that it faces a number of risks related to design, manufacturing, and supply chain management with respect to its consumer hardware products, including Reality Labs devices. The company noted that it relies on third parties to manufacture and manage the logistics of transporting and distributing its consumer hardware products, which subjects it to risks that have been exacerbated as a result of the COVID-19 pandemic. Meta stated that it has experienced, and may in the future experience, supply or labor shortages or other disruptions in logistics and the supply chain, which could result in shipping delays and negatively impact its operations, product development, and sales. The company further noted it could be negatively affected if it is not able to engage third parties with the necessary capabilities or capacity on reasonable terms, and that consumer hardware products have had quality issues resulting from design or manufacture, sometimes caused by components purchased from other manufacturers or suppliers."
        ),
    },

    # =========================================================================
    # Q2 — Competitive Landscape
    # =========================================================================

    {
        "id":       "Q2_Apple_2024",
        "type":     "risk_qualitative",
        "question": "How did Apple describe its competitive landscape in its FY2024 10-K, "
                    "particularly regarding AI-enabled smartphones and services competition?",
        "companies": ["Apple"],
        "years":    [2024],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "competition", "smartphone", "artificial intelligence", "services",
            "Android", "Google", "Samsung", "streaming", "payments", "App Store",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 competitive environment discussion covering smartphone "
            "competition (Samsung Galaxy AI, Google Pixel AI features), services competition "
            "(Spotify vs Apple Music, Netflix vs Apple TV+, Google Pay vs Apple Pay), "
            "and any new language about AI assistant competition (Gemini vs Siri, ChatGPT). "
            "Check whether Apple explicitly named competitors by name or used general language. "
            "Note whether Apple Intelligence and on-device AI are framed as competitive "
            "differentiators or risks in the competitive context section."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Apple described its markets for products and services as highly competitive, characterized by aggressive price competition and resulting downward pressure on gross margins, frequent introduction of new products and services, short product life cycles, evolving industry standards, and continual improvement in product price and performance characteristics. The company noted that many competitors seek to compete primarily through aggressive pricing and very low cost structures, and by imitating Apple's products and infringing on its intellectual property. Apple stated that it is focused on expanding its market opportunities related to smartphones, personal computers, tablets, wearables and accessories, and services, facing substantial competition from companies that have significant technical, marketing, distribution and other resources, as well as established hardware, software, and service offerings with large customer bases. The company further noted that competition has been particularly intense as competitors have aggressively cut prices and lowered product margins, with certain competitors having resources, experience or cost structures to provide products at little or no profit or even at a loss."
        ),
    },

    {
        "id":       "Q2_Microsoft_2023",
        "type":     "risk_qualitative",
        "question": "How did Microsoft characterize the competitive dynamics in cloud and "
                    "AI services in its FY2023 10-K?",
        "companies": ["Microsoft"],
        "years":    [2023],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "competition", "cloud", "Azure", "Amazon", "Google", "artificial intelligence",
            "OpenAI", "Copilot", "enterprise", "market share",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 competitive section discussion of Azure vs AWS vs Google Cloud "
            "market positioning, new AI-era competitive dynamics following the OpenAI "
            "partnership and ChatGPT launch (Jan 2023), Copilot competition against Google "
            "Workspace AI and Salesforce Einstein, and productivity suite competition (Teams "
            "vs Slack/Zoom post-pandemic). Note any language about Microsoft's AI-first "
            "strategy as a competitive moat. Check whether Microsoft disclosed its cloud "
            "market share percentage or kept language directional."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Microsoft described Azure as uniquely offering hybrid consistency, developer productivity, AI capabilities, and trusted security and compliance at global scale, while integrating across the technology stack and offering openness, improved time to value, reduced costs, and increased agility. The company highlighted its Azure AI platform as helping organizations transform by bringing intelligence and insights to employees and customers to solve pressing challenges, with organizations deploying Azure AI solutions to achieve more at scale. Microsoft disclosed its long-term partnership with OpenAI, noting that as OpenAI's exclusive cloud provider, Azure powers all of OpenAI's workloads, and that the company has increased investments in specialized supercomputing systems to accelerate OpenAI's research. The company also described its Copilot integration across Microsoft 365, GitHub Copilot, and other enterprise platforms as central to its competitive AI strategy against rivals in the cloud and productivity markets."
        ),
    },

    {
        "id":       "Q2_Google_2023",
        "type":     "risk_qualitative",
        "question": "How did Alphabet describe the competitive threat to its Search business "
                    "from AI-powered alternatives in its FY2023 10-K?",
        "companies": ["Google"],
        "years":    [2023],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "competition", "Search", "artificial intelligence", "large language model",
            "ChatGPT", "Bing", "Microsoft", "generative AI", "advertising", "query",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A risk factor language about competition in the search market "
            "from AI-powered alternatives, specifically the threat from Microsoft Bing with "
            "ChatGPT integration (launched Feb 2023). Note whether Alphabet named Microsoft "
            "and OpenAI explicitly or used general 'new technologies' language. Check Item 1 "
            "for framing of Bard and Gemini as competitive responses. Note how Google balances "
            "acknowledging AI search risk against its dominant market position — look for "
            "hedging language patterns. Compare AI risk language intensity vs FY2022."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Alphabet disclosed that it generated more than 75% of total revenues from online advertising and faces risk that partners including advertisers, distribution partners, digital publishers, and content providers can terminate contracts at any time. The company noted that technologies have been developed that make customized ads more difficult or block the display of ads altogether, and that some providers of online services have integrated these technologies that could impair the availability and functionality of third-party digital advertising. Alphabet also disclosed that many websites violate or attempt to violate its guidelines, including by seeking to inappropriately rank higher in search results, and that increased use of AI in its offerings and internal systems may create new avenues of abuse for bad actors. The company acknowledged that its revenue growth rate and expense as a percentage of revenues may differ significantly from historical rates, as it faces increasing competition for user engagement and advertisers from AI-powered alternatives and other platforms."
        ),
    },

    {
        "id":       "Q2_Amazon_2023",
        "type":     "risk_qualitative",
        "question": "How did Amazon describe its competitive landscape in its FY2023 10-K, "
                    "covering retail, cloud, and advertising segments?",
        "companies": ["Amazon"],
        "years":    [2023],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "competition", "retail", "AWS", "cloud", "advertising", "Microsoft", "Google",
            "Walmart", "marketplace", "Prime", "third-party sellers",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 competitive analysis covering three distinct business lines — "
            "retail (Walmart.com, Temu, Shein, Target), cloud (Microsoft Azure, Google Cloud, "
            "and international cloud providers), advertising (Google, Meta, emerging retail "
            "media). Note whether Amazon's competitive moat language (Prime loyalty, seller "
            "ecosystem, AWS infrastructure) changed from FY2022. Check for new language "
            "about AI-powered shopping features as competitive differentiators. Look for "
            "any mention of Temu or fast-fashion Chinese competitors disrupting marketplace."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Amazon described its worldwide marketplace as evolving rapidly and intensely competitive, with a broad array of competitors from many different industry sectors around the world. The company noted that its current and potential competitors include physical, e-commerce, and omnichannel retailers, publishers, vendors, distributors, manufacturers, and producers of the products it offers and sells to consumers and businesses, as well as web search engines, comparison shopping websites, social networks, web portals, and other online and app-based means of discovering and acquiring goods and services. Amazon disclosed that it also competes with providers of enterprise IT infrastructure services in the cloud computing market, including Microsoft Azure and Google Cloud. The company stated that the worldwide marketplace is characterized by rapid change in technologies and business models, and that many competitors have longer operating histories, larger customer bases, greater brand recognition, and significantly greater financial, marketing, and other resources."
        ),
    },

    {
        "id":       "Q2_Meta_2022",
        "type":     "risk_qualitative",
        "question": "How did Meta describe the competitive threat from TikTok and short-form "
                    "video in its FY2022 10-K, and what was the company's strategic response?",
        "companies": ["Meta"],
        "years":    [2022],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "competition", "TikTok", "short-form video", "Reels", "engagement",
            "user attention", "time spent", "advertising", "ByteDance", "youth",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A risk language explicitly naming TikTok (and ByteDance) as "
            "a competitive threat to user engagement and advertising revenue, discussion "
            "of Reels as Meta's strategic response and whether its monetization rate lagged "
            "Feed/Stories, language about younger demographic engagement shifting away from "
            "Facebook and Instagram toward TikTok, and any mention of regulatory risk "
            "that could affect TikTok (potential ban benefiting Meta). Compare the specificity "
            "of competitive language in FY2022 vs FY2021 when TikTok threat first appeared."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Meta disclosed that competitive products and services, such as TikTok, have reduced some users' engagement with its products and services, alongside global and regional business, macroeconomic, and geopolitical conditions. The company noted that the COVID-19 pandemic had led to increases and decreases in the size and engagement of its active user base from period to period, and that in connection with the war in Ukraine, access to Facebook and Instagram was restricted in Russia, contributing to declines in the number of DAUs and MAUs in Europe. Meta disclosed that if people do not perceive its products to be useful, reliable, and trustworthy, the company may not be able to attract or retain users or maintain the frequency and duration of their engagement, noting that a number of other social networking companies that achieved early popularity have since seen their active user bases or levels of engagement decline. The company further acknowledged that Reels, its short-form video response to TikTok, was growing in usage but monetizes at a lower rate than feed and Stories products."
        ),
    },

    # =========================================================================
    # Q3 — Macroeconomic Risks
    # =========================================================================

    {
        "id":       "Q3_Apple_2023",
        "type":     "risk_qualitative",
        "question": "What macroeconomic risks did Apple highlight in its FY2023 10-K, "
                    "including foreign exchange headwinds and consumer demand uncertainty?",
        "companies": ["Apple"],
        "years":    [2023],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "macroeconomic", "foreign exchange", "currency", "consumer spending",
            "inflation", "interest rate", "Greater China", "economic slowdown", "demand",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A and Item 7 discussion of strong US dollar headwinds on "
            "international revenue (especially Greater China and Europe), consumer "
            "discretionary spending slowdown affecting premium hardware demand, inflation's "
            "impact on production costs, and Greater China macro uncertainty (post-COVID "
            "reopening volatility). Note whether Apple quantified FX impact on revenue "
            "in constant currency terms in Item 7. Check for any language about interest "
            "rate sensitivity given Apple's large investment portfolio and share buyback program."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Apple disclosed that its primary exposure to movements in foreign exchange rates relates to non-U.S. dollar-denominated sales, cost of sales and operating expenses worldwide, with gross margins on products in foreign countries and on products that include components obtained from foreign suppliers having been materially adversely affected by foreign exchange rate fluctuations. The company noted that the weakening of foreign currencies relative to the U.S. dollar adversely affects the U.S. dollar value of the company's foreign currency-denominated sales and earnings, and generally leads the company to raise international pricing, potentially reducing demand. Apple further noted that adverse macroeconomic conditions, including inflation, slower growth or recession, new or increased tariffs and other barriers to trade, changes to fiscal and monetary policy, tighter credit, higher interest rates, high unemployment and currency fluctuations could materially adversely affect demand for its products and services, with consumer confidence and spending also potentially adversely affected in response to financial market volatility and other economic factors."
        ),
    },

    {
        "id":       "Q3_Microsoft_2022",
        "type":     "risk_qualitative",
        "question": "What macroeconomic risks did Microsoft highlight in its FY2022 10-K, "
                    "and how did foreign exchange and rising interest rates feature in the outlook?",
        "companies": ["Microsoft"],
        "years":    [2022],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "macroeconomic", "foreign exchange", "currency", "inflation", "interest rate",
            "PC market", "enterprise spending", "Russia", "Ukraine", "geopolitical",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A risk language around strong USD impacting international revenue "
            "(Microsoft disclosed ~$1.6B FX headwind in FY2022), rising interest rates affecting "
            "enterprise IT spending decisions and customer borrowing costs, inflationary pressure "
            "on operating costs and employee compensation, and geopolitical risk from the "
            "Russia-Ukraine war (Microsoft suspended Russia operations Mar 2022 — check for "
            "specific language). Also look for PC market softening language affecting More "
            "Personal Computing — PC shipments fell sharply in H2 FY2022."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Microsoft disclosed that its global business exposes it to operational and economic risks, with results of operations potentially affected by global, regional, and local economic developments, monetary policy, inflation, and recession, as well as political and military disputes. The company noted that its international growth strategy includes certain markets whose developing nature presents risks including deterioration of social, political, labor, or economic conditions in a country or region, and difficulties in staffing and managing foreign operations. Microsoft flagged that emerging nationalist and protectionist trends and concerns about human rights and political expression in specific countries may significantly alter the trade and commercial environments, with changes to trade policy or agreements potentially resulting in higher tariffs, local sourcing initiatives, non-local sourcing restrictions, export controls, and investment restrictions. The company also noted that laws and regulations related to climate change may increase the costs of powering and cooling computer hardware used to develop software and provide cloud-based services."
        ),
    },

    {
        "id":       "Q3_Google_2022",
        "type":     "risk_qualitative",
        "question": "How did Alphabet describe macroeconomic risks affecting its advertising "
                    "business in its FY2022 10-K, particularly the digital ad market slowdown?",
        "companies": ["Google"],
        "years":    [2022],
        "section":  "Item 7",
        "covid_related": False,
        "keywords": [
            "macroeconomic", "advertising", "digital advertising", "inflation",
            "foreign exchange", "recession", "ad spend", "currency", "slowdown", "budget",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 7 MD&A discussion of advertising revenue slowdown in H2 FY2022 "
            "(Search and YouTube growth decelerated sharply), advertiser budget cuts in "
            "response to economic uncertainty, foreign exchange headwinds on international "
            "advertising revenue, YouTube ad revenue declining year-over-year in Q3/Q4. "
            "Note how Google characterized the macro environment — did it use 'recession' "
            "language or softer terms like 'uncertainty'? Check for any forward-looking "
            "language about ad market recovery expectations. Contrast with FY2021 language."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Alphabet disclosed that its advertising revenues are affected by general economic conditions and various external dynamics, including geopolitical events, regulations, and their effect on advertiser, consumer, and enterprise spending, and that revenues generated from advertising had faced particular pressure after the outsized growth during the COVID-19 pandemic. The company noted that it faces increasing competition for user engagement and advertisers, which may affect its revenues, and that users continue to access its products using diverse devices and modalities which allows for new advertising formats that may benefit revenues but adversely affect margins. Alphabet disclosed that margins from mobile channels and newer products have generally been lower than those from traditional desktop search, and that growth in the global smartphone market has slowed due to market saturation in developed countries, which can affect mobile advertising revenues. The company also flagged that fluctuations in advertising revenues have been and may continue to be affected by factors including foreign exchange rate movements, macroeconomic uncertainty, and changes in advertiser budget allocations."
        ),
    },

    {
        "id":       "Q3_Amazon_2022",
        "type":     "risk_qualitative",
        "question": "What macroeconomic risks did Amazon describe in its FY2022 10-K, "
                    "including consumer spending shifts and rising operating costs?",
        "companies": ["Amazon"],
        "years":    [2022],
        "section":  "Item 7",
        "covid_related": False,
        "keywords": [
            "macroeconomic", "consumer spending", "inflation", "operating costs",
            "energy", "labor", "fulfillment", "interest rate", "foreign exchange", "recession",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 7 discussion of consumer shift from goods to services post-COVID "
            "(reversing the pandemic demand surge that over-provisioned Amazon's network), "
            "inflationary pressure on fulfillment costs (labor wages, energy, transportation), "
            "Amazon's significant operating cost expansion from the rapid capacity build "
            "(2020-2021) now creating fixed-cost drag, and interest rate sensitivity on "
            "Amazon's large debt portfolio. Note the Rivian equity write-down ($12.7B) as "
            "a macro-adjacent risk item. Check for language about AWS demand resilience vs "
            "consumer/advertising segment macro sensitivity."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Amazon disclosed that fulfillment costs increased in absolute dollars in 2022 compared to the prior year, primarily due to increased investment in its fulfillment network, transportation costs, and wage rates and incentives, with these costs as a percentage of net sales varying due to factors such as payment processing, productivity, volume and weight of units, and the extent of Fulfillment by Amazon services. The company reported that the North America operating segment generated an operating loss in 2022, compared to operating income in the prior year, primarily due to increased fulfillment and shipping costs from investments in its fulfillment network, transportation costs, and wage rates. Amazon noted that AWS operating income increased to $22.8 billion in 2022, compared to $18.5 billion in 2021, providing a significant offset to losses in other segments. The company disclosed that consolidated operating income was $12.2 billion in 2022 compared to $24.9 billion in 2021, reflecting the impact of macro-driven cost increases across its consumer business."
        ),
    },

    {
        "id":       "Q3_Meta_2022",
        "type":     "risk_qualitative",
        "question": "How did Meta characterize the macroeconomic headwinds affecting its "
                    "advertising business in its FY2022 10-K, and what was management's outlook?",
        "companies": ["Meta"],
        "years":    [2022],
        "section":  "Item 7",
        "covid_related": False,
        "keywords": [
            "macroeconomic", "advertising", "digital advertising", "iOS", "ATT",
            "signal loss", "foreign exchange", "currency", "advertiser", "slowdown",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 7 discussion of the 'triple headwinds' impacting Meta FY2022 — "
            "(1) digital advertising macro recession, (2) iOS ATT signal loss reducing ad "
            "targeting effectiveness, (3) TikTok competition for engagement. Note revenue "
            "decline of 1% YoY ($116.6B vs $117.9B) — how does management explain this? "
            "Check for foreign exchange headwind disclosure (USD strength hit international). "
            "Also look for Year of Efficiency language if it appears in FY2022 10-K (Zuckerberg "
            "announced in Oct 2022). Look for whether Meta quantified the ATT signal loss "
            "impact in dollar terms in MD&A."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Meta disclosed that its advertising revenue was adversely affected in 2022 and expected to continue to be affected in the foreseeable future by a combination of trends including competitive products and services such as TikTok reducing user engagement, as well as global and regional business, macroeconomic, and geopolitical conditions. The company noted that the COVID-19 pandemic had a varied impact on user growth and engagement, and that while the pandemic had initially contributed to an acceleration in the growth of online commerce increasing advertising demand, that growth had since declined with continued softening of advertising demand in 2022 as activities that shifted online during lockdowns resumed in person. Meta disclosed that it does not have perfect visibility into the factors driving advertiser spending decisions and that trends impacting advertising spend are dynamic and interrelated, making it difficult to identify with precision which factors are attributable to which trends. The company further noted uncertainty around the impact of Apple's iOS privacy changes on its ability to target and measure advertising effectiveness."
        ),
    },

    # =========================================================================
    # Q4 — New or Escalated Risks in FY2020  (all covid_related=True)
    # =========================================================================

    {
        "id":       "Q4_Apple_2020",
        "type":     "risk_qualitative",
        "question": "What new risks appeared in Apple's FY2020 10-K that were not present "
                    "or significantly escalated due to COVID-19?",
        "companies": ["Apple"],
        "years":    [2020],
        "section":  "Item 1A",
        "covid_related": True,
        "keywords": [
            "COVID-19", "pandemic", "supply chain disruption", "store closure",
            "remote work", "manufacturing", "health and safety", "demand uncertainty",
        ],
        "ground_truth_placeholder": (
            "Look for: new dedicated COVID-19 risk factor section (compare section "
            "headings against FY2019 10-K — new headers = new risks), language about "
            "retail store closures and their impact on direct-to-consumer revenue, "
            "manufacturing disruption in China (Foxconn Zhengzhou facility language), "
            "uncertainty about consumer demand for premium hardware, employee health "
            "and safety protocols. Also check for first appearance of 'work from home' "
            "or 'remote work' language. Note whether Apple quantified pandemic revenue "
            "impact or kept language qualitative and forward-looking."
        ),
        "ground_truth": (
            "In its FY2020 10-K, Apple disclosed that its business, results of operations, financial condition and stock price have been adversely affected and could in the future be materially adversely affected by the COVID-19 pandemic, which has spread rapidly throughout the world and prompted governments and businesses to take unprecedented measures including restrictions on travel and business operations, temporary closures of businesses, and quarantines and shelter-in-place orders. The company stated that following the initial outbreak of the virus, it experienced disruptions to its manufacturing, supply chain and logistical services provided by outsourcing partners, resulting in temporary iPhone supply shortages that affected sales worldwide. Apple noted that during the course of the pandemic, its retail stores as well as channel partner points of sale have been temporarily closed at various times, and where stores and points of sale have reopened they are subject to operating restrictions to protect public health and the health and safety of employees and customers. The company further stated that it has at times required substantially all of its employees to work remotely, and that the full extent of the pandemic's impact on its operational and financial performance remains uncertain, depending on factors outside the company's control including the timing, extent, trajectory and duration of the pandemic."
        ),
    },

    {
        "id":       "Q4_Microsoft_2020",
        "type":     "risk_qualitative",
        "question": "What new risks and opportunities appeared in Microsoft's FY2020 10-K "
                    "linked to the COVID-19 pandemic, and how did remote work reshape the risk profile?",
        "companies": ["Microsoft"],
        "years":    [2020],
        "section":  "Item 1A",
        "covid_related": True,
        "keywords": [
            "COVID-19", "pandemic", "remote work", "Teams", "cloud", "demand surge",
            "security", "capacity", "health and safety", "business continuity",
        ],
        "ground_truth_placeholder": (
            "Look for: COVID-19 specific risk section (new in FY2020 vs FY2019), language "
            "about unprecedented Teams demand surge (March 2020 daily active users went "
            "from 32M to 75M+ in two weeks — check if Microsoft disclosed this). Note "
            "the paradox of COVID as both risk (customer financial distress, contract "
            "cancellations) and demand accelerant (cloud adoption pull-forward). Check for "
            "security risk language — remote work expanded the attack surface. Also look "
            "for capacity risk language (Azure had to manage rapid demand spikes) and any "
            "supply chain language about data center hardware procurement."
        ),
        "ground_truth": (
            "In its FY2020 10-K, Microsoft disclosed that the COVID-19 pandemic is having widespread, rapidly evolving, and unpredictable impacts on global society, economies, financial markets, and business practices, with federal and state governments implementing measures including social distancing, travel restrictions, border closures, limitations on public gatherings, work from home directives, supply chain logistical changes, and closure of non-essential businesses. The company stated that to protect the health and well-being of its employees, suppliers, and customers, it made substantial modifications to employee travel policies, implemented office closures as employees are advised to work from home, and cancelled or shifted conferences and other marketing events to virtual-only through fiscal year 2021. Microsoft disclosed that in the third and fourth quarters of fiscal year 2020, it experienced adverse impacts to its supply chain, a slowdown in transactional licensing, and lower demand for its advertising services. The company noted that the extent to which the COVID-19 pandemic impacts its business going forward will depend on numerous evolving factors including the duration and scope of the pandemic, governmental and business actions in response, and the impact on economic activity including the possibility of recession or financial market instability."
        ),
    },

    {
        "id":       "Q4_Google_2020",
        "type":     "risk_qualitative",
        "question": "What new risks did Alphabet disclose in its FY2020 10-K related to "
                    "COVID-19, particularly the impact on advertising revenue and operations?",
        "companies": ["Google"],
        "years":    [2020],
        "section":  "Item 1A",
        "covid_related": True,
        "keywords": [
            "COVID-19", "pandemic", "advertising revenue", "advertiser", "travel",
            "hospitality", "uncertainty", "remote work", "data center", "health and safety",
        ],
        "ground_truth_placeholder": (
            "Look for: COVID-19 risk section (new in FY2020), language about advertising "
            "revenue cyclicality risk amplified by pandemic (travel, hospitality, retail "
            "advertiser spend collapsed in Q1/Q2 2020), uncertainty about advertising "
            "recovery timeline, any quantification of COVID impact on Q1/Q2 2020 revenue. "
            "Check for YouTube content moderation risk during pandemic (surge in health "
            "misinformation). Note Google's employee remote work transition language and "
            "any data center operational risk. Compare with FY2021 — FY2020 should have "
            "more uncertain, forward-looking language while FY2021 reflects actual recovery."
        ),
        "ground_truth": (
            "In its FY2020 10-K, Alphabet disclosed that the continuing impacts of COVID-19 are highly unpredictable and could be significant, and may have an adverse effect on its business, operations and future financial performance, as governments and municipalities around the world have instituted measures to control the spread of COVID-19 including quarantines, shelter-in-place orders, school closings, travel restrictions, and closure of non-essential businesses. The company noted that the macroeconomic impacts on its business continue to evolve and be unpredictable, and that its revenue growth rate and expense as a percentage of revenues in future periods may differ significantly from historical rates. Alphabet acknowledged that its advertising revenues are particularly exposed to macroeconomic conditions, as expenditures by advertisers tend to correlate with overall economic activity, and that certain advertiser categories such as travel, hospitality, and retail faced sharply reduced spending budgets during the pandemic. The company further stated that unforeseen effects from the COVID-19 pandemic and the global economic climate may give rise to or amplify additional risks, requiring substantial judgment in assessing and managing these evolving uncertainties."
        ),
    },

    {
        "id":       "Q4_Amazon_2020",
        "type":     "risk_qualitative",
        "question": "What new operational and workforce risks did Amazon disclose in its "
                    "FY2020 10-K related to the COVID-19 pandemic and the demand surge?",
        "companies": ["Amazon"],
        "years":    [2020],
        "section":  "Item 1A",
        "covid_related": True,
        "keywords": [
            "COVID-19", "pandemic", "worker safety", "fulfillment center", "essential worker",
            "PPE", "health protocols", "demand surge", "capacity", "workforce",
        ],
        "ground_truth_placeholder": (
            "Look for: COVID-19 specific risk language around worker health and safety in "
            "fulfillment centers (Amazon was declared 'essential' but faced significant "
            "worker safety scrutiny in 2020), PPE procurement and health protocol costs, "
            "unprecedented demand surge outstripping fulfillment capacity (Amazon hired "
            "175,000 workers in Q1 2020 alone — check if disclosed). Note the tension "
            "between COVID as demand accelerant (e-commerce surge) and operational risk "
            "(worker safety, supply chain constraints). Check for language about third-party "
            "seller inventory constraints and any reference to worker unionization risk "
            "emerging from pandemic working conditions."
        ),
        "ground_truth": (
            "In its FY2020 10-K, Amazon disclosed that in addition to the effects of the COVID-19 pandemic and resulting global disruptions on its business and operations, additional or unforeseen effects from the pandemic and the global economic climate may give rise to or amplify the risk factors facing the company. The company noted that it faces significant risks related to worker health and safety, as its fulfillment centers and logistics operations were designated as essential services, requiring implementation of extensive health protocols, procurement of personal protective equipment, and significant additional operating costs to protect employees. Amazon stated that productivity across its fulfillment network has been affected by global supply chain constraints and constrained labor markets driven by the pandemic, which increased payroll costs and made it difficult to hire, train, and deploy a sufficient number of people to operate the network efficiently. The company further disclosed that failure to adequately staff its fulfillment network and customer service centers, including during periods of unprecedented demand surges resulting from COVID-19, increases net shipping cost and may result in delays to customers."
        ),
    },

    {
        "id":       "Q4_Meta_2020",
        "type":     "risk_qualitative",
        "question": "What new risks appeared in Meta's FY2020 10-K that were not present "
                    "in prior years, including pandemic impacts and political content risks?",
        "companies": ["Meta"],
        "years":    [2020],
        "section":  "Item 1A",
        "covid_related": True,
        "keywords": [
            "COVID-19", "pandemic", "election", "content moderation", "misinformation",
            "advertiser boycott", "iOS", "privacy", "political", "health misinformation",
        ],
        "ground_truth_placeholder": (
            "Look for: COVID-19 risk section (new in FY2020), pandemic impact on advertiser "
            "spending (July 2020 advertiser boycott #StopHateForProfit involved 1,000+ brands "
            "— check if Meta/Facebook disclosed revenue impact), US election content "
            "moderation risk (2020 election year), health misinformation risk during pandemic, "
            "and first mention of Apple ATT/iOS privacy framework risk (Apple announced ATT "
            "in June 2020 WWDC, risk language may appear here before implementation). "
            "Compare section headers against FY2019 10-K — new headers reveal escalated risks. "
            "Note whether regulatory risk language (antitrust) escalated given FTC and DOJ "
            "investigations launched in 2020."
        ),
        "ground_truth": (
            "In its FY2020 10-K, Meta disclosed that the COVID-19 pandemic has had, and may in the future have, a significant adverse impact on its advertising revenue and also exposes its business to other risks, as authorities implemented numerous preventative measures causing business slowdowns or shutdowns in affected areas both regionally and worldwide. The company noted that in the second quarter of 2020, its advertising revenue grew 10% year-over-year, which was the slowest growth rate for any fiscal quarter since its initial public offering, and that while the advertising revenue growth rate improved in subsequent quarters, there is no assurance that it will not decrease again as a result of the effects of the pandemic. Meta disclosed that it believes the pandemic has contributed to an acceleration in the shift of commerce from offline to online, as well as increasing consumer demand for purchasing products as opposed to services, which in turn increased demand for its advertising services, though it is possible this increased demand may not continue in future periods and may even recede as the effects of the pandemic subside. The company also noted new risks related to content moderation during the pandemic, including health misinformation and political content challenges in an election year, as well as escalating regulatory and privacy scrutiny."
        ),
    },

    # =========================================================================
    # Q5 — AI and Machine Learning Investments
    # =========================================================================

    {
        "id":       "Q5_Apple_2024",
        "type":     "risk_qualitative",
        "question": "How did Apple describe its AI and machine learning strategy in its "
                    "FY2024 10-K, and what risks did it associate with Apple Intelligence?",
        "companies": ["Apple"],
        "years":    [2024],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "artificial intelligence", "machine learning", "Apple Intelligence",
            "Siri", "on-device", "privacy", "generative AI", "ChatGPT", "OpenAI",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 description of Apple Intelligence (launched iOS 18.1, "
            "Oct 2024) and its integration into Siri, Writing Tools, Image Playground — "
            "check for Apple's privacy-first AI framing (on-device processing, Private "
            "Cloud Compute). Check Item 1A for AI-related risks: hallucination risk, "
            "third-party AI integration risk (OpenAI ChatGPT integration in Siri), "
            "regulatory risk from EU AI Act, competitive risk if AI features lag Android. "
            "Note frequency of 'artificial intelligence' vs prior year 10-K. Also look "
            "for R&D investment narrative in Item 7 — does Apple quantify AI R&D? "
            "Check for any AI chip/Neural Engine language as a hardware differentiator."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Apple described its product lineup across iPhone, Mac, iPad, wearables, and services, with the company's Item 1A disclosing that the introduction of new and complex technologies, such as artificial intelligence features, can increase safety risks including exposing users to harmful, inaccurate or other negative content and experiences. The company noted that it designs and develops nearly the entire solution for its products, including the hardware, operating system, numerous software applications and related services, and that its ability to compete successfully depends heavily on ensuring the continuing and timely introduction of innovative new products, services and technologies to the marketplace, including AI-enhanced features. Apple disclosed that there can be no assurance it will be able to detect and fix all issues and defects in the hardware, software and services it offers, including those related to AI capabilities, and that failure to do so can result in widespread technical and performance issues affecting its products and services. The company also faces competitive pressure as rivals rapidly adopt technological advancements, including AI capabilities, which could affect Apple's market position if its own AI offerings do not meet customer expectations."
        ),
    },

    {
        "id":       "Q5_Microsoft_2024",
        "type":     "risk_qualitative",
        "question": "How did Microsoft describe its AI investment thesis and associated "
                    "risks in its FY2024 10-K, including the OpenAI partnership?",
        "companies": ["Microsoft"],
        "years":    [2024],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "artificial intelligence", "Copilot", "OpenAI", "Azure OpenAI",
            "generative AI", "large language model", "AI safety", "CapEx", "infrastructure",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 description of Copilot integration across Microsoft 365, "
            "GitHub, Azure, Dynamics — check for Microsoft 365 Copilot pricing ($30/user/month) "
            "and customer adoption language. Item 1A risks: AI safety and ethics risk, "
            "dependence on OpenAI partnership (concentration risk), regulatory risk from "
            "EU AI Act and FTC scrutiny of OpenAI investment, hallucination/reliability "
            "risk in enterprise deployments. Check Item 7 for CapEx discussion — Microsoft "
            "guided $44.5B capex in FY2024 largely for AI infrastructure. Note whether "
            "Microsoft disclosed Azure OpenAI revenue contribution or kept it bundled."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Microsoft described Microsoft 365 as an AI-first platform that brings together Office, Windows, Copilot, and Enterprise Mobility + Security to help organizations empower their employees, with Copilot for Microsoft 365 combining AI with business data in the Microsoft Graph and Microsoft 365 applications to provide role-based AI assistance. The company highlighted its long-term partnership with OpenAI as central to its AI strategy, noting it deploys OpenAI's models across its consumer and enterprise products and has made significant investments in specialized supercomputing systems to accelerate OpenAI's research as OpenAI's exclusive cloud provider. Microsoft described its Azure AI platform as helping organizations transform by bringing intelligence and insights to employees and customers, with its AI offerings spanning Azure OpenAI Service, GitHub Copilot, Copilot for Sales, Copilot for Service, and Copilot for Finance to drive operational efficiency and customer experience improvements. The company's Item 1A disclosed that its business strategy is increasingly tied to AI investments, and that risks include the performance and reliability of AI systems, regulatory developments around AI governance, and competitive dynamics with other major AI platform providers."
        ),
    },

    {
        "id":       "Q5_Google_2023",
        "type":     "risk_qualitative",
        "question": "How did Google describe its AI and machine learning investments in its "
                    "FY2023 10-K, and how did management frame the Bard and Gemini strategy?",
        "companies": ["Google"],
        "years":    [2023],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "artificial intelligence", "Bard", "Gemini", "large language model",
            "Search Generative Experience", "Vertex AI", "TPU", "machine learning", "Duet AI",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 discussion of Bard (launched Feb 2023, rebranded to Gemini), "
            "Search Generative Experience (SGE), Gemini model family (Ultra, Pro, Nano), "
            "Vertex AI enterprise platform, Duet AI in Google Workspace. Check Item 1A for "
            "AI risks: SGE could reduce Search click-through rates and harm advertising revenue "
            "(check if Google flagged this explicitly), AI hallucination risk in public-facing "
            "products, regulatory risk from EU AI Act, competitive risk if Bard lags ChatGPT. "
            "Count 'artificial intelligence' frequency vs FY2022 10-K — expect significant "
            "increase. Note R&D investment for AI in Item 7: $45.4B in FY2023 vs $39.5B FY2022."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Alphabet disclosed that in December 2023 it launched Gemini, its most capable and general model, built from the ground up to be multimodal, capable of generalizing and seamlessly understanding, operating across, and combining different types of information including text, code, audio, images, and video. The company stated that its teams across Alphabet will leverage Gemini, as well as other AI models previously developed and announced, across its business to deliver the best product and service experiences for users, advertisers, partners, customers, and developers. Alphabet described its approach to AI as both bold and responsible, having published its AI Principles in 2018 as one of the first companies to articulate principles that put beneficial use, users, safety, and avoidance of harms above business considerations, while acknowledging natural tension between being bold and being responsible. The company also highlighted significant investment in AI technical infrastructure and Google Cloud's Vertex AI platform as enabling businesses from startups to large enterprises to drive transformation through AI-powered solutions."
        ),
    },

    {
        "id":       "Q5_Amazon_2024",
        "type":     "risk_qualitative",
        "question": "How did Amazon describe its generative AI strategy and investments in "
                    "its FY2024 10-K, including Bedrock, Trainium, and Alexa AI?",
        "companies": ["Amazon"],
        "years":    [2024],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "artificial intelligence", "generative AI", "Bedrock", "Titan", "Trainium",
            "Inferentia", "Alexa", "large language model", "AWS", "foundation model",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 AWS section description of Amazon Bedrock (managed LLM service "
            "hosting Anthropic Claude, Meta Llama, Stability AI models), Titan models "
            "(Amazon's own foundation models), Trainium/Inferentia custom AI chips as cost "
            "and performance differentiators, and Alexa+ or AI-powered Alexa enhancements. "
            "Check Item 1A for AI risks: custom AI chip development risk (vs NVIDIA dependency), "
            "regulatory risk from EU AI Act, AI model liability risk, competition from Azure "
            "OpenAI and Google Vertex AI. Note Item 7 capex discussion — Amazon guided $83B "
            "capex in FY2024, heavily weighted toward AI infrastructure. Check if Amazon "
            "disclosed AWS generative AI revenue contribution."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Amazon described itself as seeking to be Earth's most customer-centric company, guided by four principles: customer obsession, passion for invention, commitment to operational excellence, and long-term thinking, with its AWS segment offering a broad set of on-demand technology services including compute, storage, database, analytics, and machine learning. The company disclosed that AWS serves developers and enterprises of all sizes, including start-ups, government agencies, and academic institutions, through its cloud platform that includes generative AI services such as Amazon Bedrock for accessing foundation models, and custom AI chips including Trainium and Inferentia designed to reduce the cost and improve the performance of AI workloads. Amazon stated that its AI initiatives span across its business segments, including AI-powered product recommendations for consumers, advertising optimization tools, Alexa voice assistant enhancements, and AWS services enabling enterprise customers to build and deploy generative AI applications. The company noted in its risk factors that competition in AI infrastructure and services is intensifying, with Microsoft Azure and Google Cloud as significant rivals in the cloud AI market."
        ),
    },

    {
        "id":       "Q5_Meta_2024",
        "type":     "risk_qualitative",
        "question": "How did Meta describe its AI strategy and the Llama open-source model "
                    "ecosystem in its FY2024 10-K, and what risks did it associate with AI?",
        "companies": ["Meta"],
        "years":    [2024],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "artificial intelligence", "Llama", "Meta AI", "generative AI",
            "open-source", "AI assistant", "Reels", "recommendation", "CapEx", "data center",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 description of Meta AI assistant (integrated across WhatsApp, "
            "Messenger, Instagram, Facebook), Llama 3 open-source release strategy (why open "
            "source — check if Meta explains the ecosystem benefit), AI-powered content "
            "recommendation improvements driving Reels engagement. Check Item 1A AI risks: "
            "generative AI content moderation failure risk, regulatory risk (EU AI Act, GDPR "
            "implications of AI training on user data), hallucination risk in Meta AI assistant, "
            "competitive risk if Llama ecosystem is adopted by rivals. Note Item 7 capex "
            "discussion — Meta guided $37-40B capex in FY2024 for AI infrastructure. "
            "Check frequency of 'artificial intelligence' vs FY2022 — expect dramatic increase."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Meta disclosed that it is innovating in artificial intelligence technologies across its products and services, with AI investments supporting initiatives including the systems that rank content in its apps, its discovery engine that recommends relevant content, the tools advertisers use to reach customers, and the development of new generative AI experiences. The company described Meta AI as an assistant available across its family of apps, on Ray-Ban Meta AI glasses, and on the web, designed to help people learn, get things done, create content, and connect with others. Meta highlighted its open-source Llama model strategy as a key element of its AI approach, releasing models that developers and researchers can use and build upon, enabling a broader ecosystem while advancing Meta's own AI capabilities. The company also noted in its risk factors that it faces significant competition from other companies developing AI features and technologies, and that its AI initiatives depend on access to data to effectively train its models, with regulatory developments including the EU AI Act creating additional compliance obligations."
        ),
    },

    # =========================================================================
    # Q6 — Revenue Outlook and Forward-Looking Guidance Language
    # =========================================================================

    {
        "id":       "Q6_Apple_2023",
        "type":     "risk_qualitative",
        "question": "How did Apple's management discuss the revenue outlook and growth "
                    "strategy in the FY2023 10-K MD&A, particularly for Services?",
        "companies": ["Apple"],
        "years":    [2023],
        "section":  "Item 7",
        "covid_related": False,
        "keywords": [
            "Services", "revenue growth", "gross margin", "installed base",
            "subscription", "App Store", "iCloud", "Apple TV+", "outlook", "guidance",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 7 discussion of Services revenue growth trajectory ($85.2B in "
            "FY2023, growing even as iPhone revenue declined), management language about "
            "installed base monetization as the growth engine, Services gross margin being "
            "significantly higher than Products (check if Apple disclosed this in MD&A). "
            "Note cautious language around total revenue ($383.3B, -3% YoY) — how does "
            "management frame this decline? Check for any guidance language about iPhone 15 "
            "launch (FY2024 product cycle) and Greater China demand recovery. Apple rarely "
            "gives explicit guidance — note how management communicates directional outlook."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Apple's MD&A disclosed that Services net sales increased 9% or $7.1 billion during 2023 compared to 2022 due to higher net sales across all lines of business, even as total company net sales declined. The company reported that Services gross margin percentage was 70.8% in FY2023 compared to 36.5% for Products, highlighting the significantly higher-margin profile of its services segment including the App Store, iCloud, Apple Music, Apple TV+, and AppleCare. Apple disclosed that Services gross margin increased during 2023 compared to 2022 due primarily to higher Services net sales, partially offset by the weakness in foreign currencies relative to the U.S. dollar and higher Services costs. The company also reported that Products gross margin percentage increased during 2023 compared to 2022 due to cost savings and a different Products mix, partially offset by the weakness in foreign currencies relative to the U.S. dollar, indicating management's ongoing focus on margin improvement even as hardware revenue faced headwinds."
        ),
    },

    {
        "id":       "Q6_Microsoft_2023",
        "type":     "risk_qualitative",
        "question": "How did Microsoft's management discuss growth drivers and the "
                    "Copilot monetization path in the FY2023 10-K MD&A?",
        "companies": ["Microsoft"],
        "years":    [2023],
        "section":  "Item 7",
        "covid_related": False,
        "keywords": [
            "cloud", "Azure", "Copilot", "AI", "revenue growth", "commercial",
            "Intelligent Cloud", "operating leverage", "Microsoft 365", "outlook",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 7 discussion of Azure growth rate (which decelerated to ~27% "
            "in FY2023 from ~40% in FY2022), management explanation for deceleration "
            "(consumption-based model, enterprise optimization), Copilot preview launch "
            "and early commercial signals, Microsoft 365 Copilot pricing announcement. "
            "Check for operating leverage discussion — operating margin reached 41.8% "
            "despite Activision deal costs. Note language about Intelligent Cloud being "
            "the growth engine vs More Personal Computing headwinds (PC market). Look "
            "for management confidence language around AI monetization acceleration in FY2024."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Microsoft's MD&A reported that server products and cloud services revenue increased 19% driven by Azure and other cloud services growth of 29%, while Dynamics 365 growth reached 24%, reflecting strong momentum in its Intelligent Cloud segment. The company disclosed that Windows OEM revenue decreased 25% and Devices revenue decreased 24%, highlighting the contrast between its declining PC-related businesses and its growing cloud and AI segments. Microsoft described its strategy of integrating Copilot for Microsoft 365, GitHub Copilot, and other AI offerings as central to its growth narrative, with the company positioning itself as an AI-first platform provider across productivity, cloud, and enterprise markets. The company also noted industry trends showing that each industry shift is an opportunity to conceive new products, new technologies, or new ideas that can further transform the industry, with Microsoft investing in AI infrastructure and capabilities as the primary driver of future revenue growth."
        ),
    },

    {
        "id":       "Q6_Google_2022",
        "type":     "risk_qualitative",
        "question": "How did Alphabet's management characterize the revenue outlook in the "
                    "FY2022 10-K MD&A, given the advertising market slowdown?",
        "companies": ["Google"],
        "years":    [2022],
        "section":  "Item 7",
        "covid_related": False,
        "keywords": [
            "advertising", "revenue growth", "YouTube", "Search", "Google Cloud",
            "operating expenses", "headcount", "efficiency", "slowdown", "outlook",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 7 MD&A management discussion of YouTube revenue declining YoY "
            "in H2 2022 (Q3: -2%, Q4: -8% YoY), Search revenue deceleration (still grew "
            "but slowed to ~7% from ~43% in FY2021), and Google Cloud continuing to grow "
            "at 37% despite macro headwinds. Look for efficiency language — Alphabet began "
            "its cost-cutting narrative in FY2022 (headcount grew to 186,779 but this was "
            "the peak). Note whether management used the word 'recession' in MD&A, and how "
            "they explained the operating margin decline (26.5% vs 30.6% in FY2021). "
            "Check for Google Cloud profitability timeline discussion."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Alphabet's MD&A disclosed that its advertising revenues are affected by general economic conditions and various external dynamics including geopolitical events, regulations, and their effect on advertiser, consumer, and enterprise spending, with particular pressure experienced after the outsized growth during the COVID-19 pandemic. The company noted that revenues from ads on YouTube and Google Play monetize at a lower rate than traditional search ads, and that development of new products incorporating AI innovations could affect monetization trends. Alphabet disclosed that Google Services revenues, comprising Google advertising and Google other revenues, are the primary revenue driver, with Google advertising revenues including Google Search, YouTube ads, and Google Network revenues across AdMob, AdSense, and Google Ad Manager. The company also highlighted the shift to mobile and diverse devices as creating opportunities for new advertising formats that may benefit revenues but adversely affect margins, particularly as growth in the global smartphone market has slowed due to increased market saturation in developed countries."
        ),
    },

    {
        "id":       "Q6_Amazon_2022",
        "type":     "risk_qualitative",
        "question": "How did Amazon's management explain the FY2022 operating income "
                    "trough and the revenue outlook in the FY2022 10-K MD&A?",
        "companies": ["Amazon"],
        "years":    [2022],
        "section":  "Item 7",
        "covid_related": False,
        "keywords": [
            "operating income", "fulfillment", "overcapacity", "efficiency",
            "AWS", "advertising", "cost reduction", "headcount", "outlook", "margin",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 7 explanation of operating income trough ($12.2B operating income "
            "vs $24.9B in FY2021) — management should explain the two-year over-investment in "
            "fulfillment capacity (built for COVID demand that normalized) creating fixed-cost "
            "inefficiency. Note the Rivian equity write-down ($12.7B) causing net loss — "
            "check if management separates operating vs net income in the narrative. Look "
            "for AWS growth normalization explanation (declined from 37% to 29% YoY), and "
            "advertising services as the bright spot (growing 19% to $37.7B). Check for "
            "headcount reduction language (Amazon began layoffs late 2022 — check if FY2022 "
            "10-K references the 18K layoff announcement)."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Amazon's MD&A reported that consolidated operating income was $12.2 billion for 2022 compared to $24.9 billion for 2021, with the company noting that operating income is a more meaningful measure than gross profit and gross margin due to the diversity of its product categories and services. The company disclosed that the North America segment generated an operating loss in 2022, as compared to operating income in the prior year, primarily due to increased fulfillment and shipping costs from investments in its fulfillment network, transportation costs, and wage rates and incentives, increased technology and content costs, and growth in certain operating expenses. Amazon reported that AWS operating income increased to $22.8 billion in 2022 from $18.5 billion in 2021, serving as the primary profit driver for the consolidated company while its consumer businesses absorbed the costs of over-investment in fulfillment capacity built during the pandemic demand surge. The company also highlighted advertising services as a significant revenue contributor growing within its business, partially offsetting headwinds in its North America and International retail segments."
        ),
    },

    {
        "id":       "Q6_Meta_2023",
        "type":     "risk_qualitative",
        "question": "How did Meta's management discuss the Year of Efficiency outcomes and "
                    "the advertising recovery in the FY2023 10-K MD&A?",
        "companies": ["Meta"],
        "years":    [2023],
        "section":  "Item 7",
        "covid_related": False,
        "keywords": [
            "Year of Efficiency", "operating income", "margin", "headcount",
            "advertising", "Reels", "monetization", "AI", "cost reduction", "outlook",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 7 narrative on Year of Efficiency execution — headcount reduction "
            "from 86.5K (FY2022) to 67.3K (FY2023), operating income recovery to $46.8B "
            "(vs $28.9B in FY2022), and advertising revenue rebound to $131.9B. Check "
            "for management language about Reels monetization closing the gap with Feed/Stories "
            "(Reels monetization efficiency was a key FY2023 narrative). Note how management "
            "frames Reality Labs losses ($13.7B in FY2023) in the context of long-term "
            "metaverse investment vs short-term profitability. Look for language about "
            "AI-driven ad targeting improvements post-iOS ATT impact as a recovery driver."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Meta's MD&A reported that total revenue for 2023 was $134.90 billion, an increase of 16% compared to 2022, due to an increase in advertising revenue, with ad impressions delivered across its Family of Apps increasing 28% year-over-year in 2023, partially offset by a 9% year-over-year decrease in the average price per ad. The company reported that income from operations for 2023 was $46.75 billion, an increase of $17.81 billion or 62% compared to 2022, reflecting the significant impact of its cost reduction efforts initiated in 2022. Meta disclosed that it expects to continue to build on the discipline and habits developed in 2022 when it initiated several efforts to increase operating efficiency, while remaining focused on investing in significant opportunities, with 80% of its total costs and expenses in 2023 recognized in the Family of Apps segment. The company also noted that its FoA investments include significant investments in AI initiatives to recommend relevant content across its products, enhance advertising tools, develop new products, and create new features, while Reels continues to grow in usage but monetizes at a lower rate than feed and Stories products."
        ),
    },

    # =========================================================================
    # Q7 — Regulatory and Antitrust Risks
    # =========================================================================

    {
        "id":       "Q7_Apple_2024",
        "type":     "risk_qualitative",
        "question": "What App Store regulatory and antitrust risks did Apple disclose in "
                    "its FY2024 10-K, including EU Digital Markets Act compliance?",
        "companies": ["Apple"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "App Store", "Digital Markets Act", "DMA", "antitrust", "DOJ",
            "sideloading", "payment processing", "developer", "regulation", "EU",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A and Item 3 risk language about the EU Digital Markets Act "
            "requiring Apple to allow third-party app stores and alternative payment processors "
            "on iOS in Europe (effective March 2024), US Department of Justice antitrust "
            "lawsuit filed March 2024 targeting iPhone ecosystem lock-in, Epic Games lawsuit "
            "appeal, and any disclosure of the financial impact of required App Store changes. "
            "Check whether Apple quantified potential revenue loss from DMA compliance changes. "
            "Look for Item 3 Legal Proceedings section for active regulatory/antitrust cases. "
            "Note how Apple frames these as risks vs. manageable compliance requirements."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Apple disclosed in its Legal Proceedings section that on March 25, 2024, the European Commission announced it had opened two formal noncompliance investigations against the company under the Digital Markets Act (DMA), concerning (1) how developers may communicate and promote offers to end users for apps distributed through the App Store as well as how developers may conclude contracts with end users; and (2) default settings, uninstallation of apps, and a web browser choice screen on iOS. The company further disclosed that on June 24, 2024, the Commission announced its preliminary findings in the Article 5(4) investigation alleging that Apple's App Store rules are in breach of the DMA, and that the Commission opened a third formal investigation regarding whether Apple's new contractual requirements for third-party app developers and app marketplaces may violate the DMA. Apple noted that if the Commission makes a final determination of a violation, it can issue a cease and desist order and may impose fines up to 10% of the company's annual worldwide net sales, with any decision appealable to the General Court of the EU but the effectiveness of the Commission's order applying immediately while under appeal."
        ),
    },

    {
        "id":       "Q7_Microsoft_2023",
        "type":     "risk_qualitative",
        "question": "What regulatory risks did Microsoft disclose in its FY2023 10-K, "
                    "including antitrust scrutiny of the Activision-Blizzard acquisition?",
        "companies": ["Microsoft"],
        "years":    [2023],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "Activision", "antitrust", "FTC", "CMA", "regulatory approval",
            "cloud gaming", "competition", "acquisition", "consent decree", "remedy",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A and Item 3 discussion of the $68.7B Activision-Blizzard "
            "acquisition regulatory battle — FTC attempted to block it (FTC v. Microsoft), "
            "UK CMA initially blocked it (April 2023), EU approved it with cloud gaming "
            "remedies (May 2023), deal ultimately closed Oct 2023. Check for language about "
            "cloud gaming market concentration risk (Game Pass + Activision + Xbox). Look "
            "for regulatory risk to Azure and AI businesses — EU AI Act drafting was active "
            "in FY2023. Note any language about OpenAI partnership drawing regulatory scrutiny "
            "(FTC investigated in July 2023). Check Item 3 for pending regulatory proceedings."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Microsoft disclosed that in January 2022 it announced a definitive agreement to acquire Activision Blizzard, Inc. for $68.7 billion, and that acquisitions and other transactions involve significant challenges and risks including that they do not advance its business strategy, result in an unsatisfactory return on investment, raise new compliance-related obligations, or cause difficulty integrating and retaining new employees, business systems, and technology. The company noted that the success of its transactions and arrangements will depend in part on its ability to leverage them to enhance existing products and services or develop compelling new ones, as well as on acquired companies' ability to meet Microsoft's policies and processes in areas such as data governance, privacy, and cybersecurity. Microsoft also disclosed that it may not achieve significant revenue from new product, service, and distribution channel investments for several years, if at all, and that new products and services may not be profitable, with operating margins for some new products and businesses potentially not as high as margins achieved historically. The company further noted that perceptions of mismanagement, driven by regulatory activity or negative public reaction to its practices or product experiences, could negatively impact product and feature adoption, product design, and product quality."
        ),
    },

    {
        "id":       "Q7_Google_2024",
        "type":     "risk_qualitative",
        "question": "How did Alphabet describe the antitrust and regulatory risks in its "
                    "FY2024 10-K, following the DOJ Search monopoly ruling?",
        "companies": ["Google"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "antitrust", "DOJ", "monopoly", "Search", "distribution agreements",
            "Digital Markets Act", "EU", "remedies", "competition", "advertising",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A and Item 3 language about the August 2024 DOJ antitrust ruling "
            "finding Google illegally monopolized the Search market (US v. Google LLC), "
            "potential remedies phase including possible forced divestiture of Chrome or "
            "Android, and required changes to search distribution agreements (Google paid "
            "Apple ~$20B/year to be default Safari search engine — check if disclosed). "
            "EU Digital Markets Act compliance for Search and Android. Note how Google "
            "frames the DOJ ruling — appeals strategy language. Check for advertising "
            "market remedies risk (potential structural separation of ad tech business). "
            "Item 3 should list all major regulatory proceedings."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Alphabet disclosed that the U.S. Department of Justice, various U.S. states, and other plaintiffs have filed, and may continue to file, several antitrust lawsuits about various aspects of its business, including its advertising technologies and practices, the operation and distribution of Google Search, and the operation and distribution of the Android operating system and Play Store. The company specifically disclosed that the DOJ and a number of state Attorneys General filed a lawsuit alleging that Google violated antitrust laws relating to Search and Search advertising, and that in August 2024, the U.S. District Court for the District of Columbia ruled that Google violated such antitrust laws. Alphabet noted that the Court is holding a separate proceeding to determine remedies, which could include alterations to its products and services and business models and operations, including structural remedies, and/or its distribution arrangements, among other changes, and that while the company plans to appeal, there can be no assurance that its appeal will succeed or that it will be able to change or decrease the severity of any remedies imposed."
        ),
    },

    {
        "id":       "Q7_Amazon_2024",
        "type":     "risk_qualitative",
        "question": "What antitrust and regulatory risks did Amazon disclose in its FY2024 "
                    "10-K, including the FTC lawsuit targeting its marketplace practices?",
        "companies": ["Amazon"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "antitrust", "FTC", "marketplace", "seller", "Prime", "fees",
            "self-preferencing", "third-party", "regulation", "competition",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A and Item 3 language about the FTC antitrust lawsuit "
            "(filed Sep 2023, active in FY2024) alleging Amazon self-preferences its own "
            "products in search results, uses anti-competitive seller fees to maintain "
            "marketplace dominance, and ties Prime benefits to coerce seller participation. "
            "Check for EU Digital Markets Act gatekeeper designation and compliance obligations. "
            "Labor regulation risk — Amazon's relationship with worker unions and NLRB "
            "proceedings. Note AWS regulatory risk from proposed cloud market regulations "
            "in EU and potential data sovereignty requirements. Check Item 3 for all active "
            "regulatory and legal proceedings."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Amazon disclosed that it is subject to governmental regulations and other legal obligations related to competition and antitrust, privacy, data use, data protection, data security, data localization, network security, consumer protection, commercial disputes, goods and services offered by it and by third parties including artificial intelligence technologies, and other matters, and that the number and scale of these proceedings have increased over time as its businesses have expanded. The company specifically noted that it is litigating a number of matters alleging price fixing, monopolization, and consumer protection claims, including those brought by state attorneys general and the Federal Trade Commission. Amazon disclosed that any of these types of proceedings can have an adverse effect through legal costs, disruption of operations, diversion of management resources, negative publicity, and other factors, and that outcomes are inherently unpredictable and subject to significant uncertainties. The company further noted that a resolution could involve licenses, sanctions, consent decrees, or orders requiring substantial future payments, preventing it from offering certain products or services, or requiring changes to its business practices in a manner materially adverse to its business."
        ),
    },

    {
        "id":       "Q7_Meta_2023",
        "type":     "risk_qualitative",
        "question": "What regulatory and privacy law risks did Meta disclose in its FY2023 "
                    "10-K, including GDPR enforcement and EU-US data transfer issues?",
        "companies": ["Meta"],
        "years":    [2023],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "GDPR", "data privacy", "EU-US", "Data Privacy Framework", "DPC",
            "Ireland", "data transfer", "fine", "regulation", "FTC consent decree",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A and Item 3 discussion of Irish DPC (Data Protection Commission) "
            "enforcement actions — the May 2023 €1.2B GDPR fine for Facebook data transfers "
            "to the US (largest GDPR fine ever at that time), the new EU-US Data Privacy "
            "Framework (adopted July 2023) enabling continued data flows. Check for FTC "
            "consent decree compliance costs (2019 $5B FTC settlement ongoing obligations). "
            "Children's privacy risk — COPPA enforcement and Kids Messenger scrutiny. "
            "EU Digital Markets Act requirements for WhatsApp interoperability. Note whether "
            "Meta disclosed a dollar range for potential future regulatory fines. "
            "Compare regulatory risk section length vs FY2022 — should be substantially longer."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Meta disclosed that on May 12, 2023, the Irish Data Protection Commission (IDPC) issued a Final Decision concluding that Meta Platforms Ireland's reliance on Standard Contractual Clauses in respect of certain transfers of European Economic Area Facebook user data was not in compliance with the GDPR, and issued an administrative fine of EUR 1.2 billion as well as corrective orders requiring Meta Platforms Ireland to suspend the relevant transfers and bring its processing operations into compliance. The company noted that it is appealing this decision and that the corrective orders are currently subject to an interim stay from the Irish High Court. Meta also disclosed that on March 25, 2022, the European Union and United States announced that they had reached an agreement in principle on a new EU-U.S. Data Privacy Framework, and that on June 30, 2023, the EEA countries were designated by the United States Attorney General as qualifying states, providing a mechanism for continued transatlantic data transfers. The company acknowledged that data privacy regulatory developments, including GDPR enforcement actions and evolving data transfer frameworks, represent a significant and ongoing legal and financial risk to its business operations."
        ),
    },

    # =========================================================================
    # Q8 — Workforce Strategy and Talent Risk  (2022-2023 layoff context)
    # =========================================================================

    {
        "id":       "Q8_Apple_2023",
        "type":     "risk_qualitative",
        "question": "How did Apple describe its workforce strategy and talent risk in its "
                    "FY2023 10-K, and why did Apple avoid mass layoffs unlike peers?",
        "companies": ["Apple"],
        "years":    [2023],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "employees", "talent", "retention", "compensation", "hiring",
            "culture", "human capital", "diversity", "engineering", "workforce",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 Human Capital section (SEC requires this since FY2020) "
            "discussing Apple's workforce composition (~161K employees), talent attraction "
            "and retention strategy, compensation philosophy (equity-heavy for engineers), "
            "diversity and inclusion metrics disclosed. Note Apple did NOT conduct mass "
            "layoffs in 2022-2023 unlike Microsoft, Google, Amazon, Meta — check if "
            "Apple addressed this implicitly in hiring freeze or 'thoughtful hiring' language. "
            "Look for engineering talent competition language (competing with Google, Meta, "
            "Microsoft for AI/ML engineers). Note any mention of Apple's return-to-office "
            "policy tensions (employees resisted mandatory hybrid in 2022-2023)."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Apple disclosed in its Human Capital section that as of September 30, 2023, the company had approximately 161,000 full-time equivalent employees, and that it believes it has a talented, motivated and dedicated team, working to create an inclusive, safe and supportive environment for all team members. The company stated that it is an equal opportunity employer committed to inclusion and diversity and to providing a workplace free of harassment or discrimination, and that it believes compensation should be competitive and equitable and should enable employees to share in the company's success. Apple noted that it recognizes its people are most likely to thrive when they have the resources to meet their needs and the time and support to succeed in their professional and personal lives, offering a wide variety of benefits for employees around the world and investing in tools and resources designed to support employees' individual growth and development. The company also indicated that it faces competition for talent, particularly in technical and engineering disciplines, requiring ongoing investment in compensation, benefits, and workplace programs to attract and retain the workforce needed to support its product and services innovation."
        ),
    },

    {
        "id":       "Q8_Microsoft_2023",
        "type":     "risk_qualitative",
        "question": "How did Microsoft characterize its workforce restructuring and talent "
                    "strategy in its FY2023 10-K following the January 2023 layoffs?",
        "companies": ["Microsoft"],
        "years":    [2023],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "employees", "restructuring", "layoffs", "talent", "workforce reduction",
            "severance", "human capital", "AI skills", "retention", "compensation",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 Human Capital discussion of the January 2023 10,000-employee "
            "layoff (check if Microsoft explicitly states the number or uses 'restructuring' "
            "language), severance costs (~$1.2B charge — check if disclosed in MD&A), "
            "and the strategic rationale (right-sizing post-COVID overhiring, reallocating "
            "resources to AI). Note remaining workforce of ~228K (FY2024) vs ~221K (FY2023) "
            "— the layoff was offset by AI-focused hiring. Look for language about AI skills "
            "reskilling programs and talent competition for AI researchers. Check Item 1A "
            "for talent risk — losing key AI researchers to OpenAI, Google, or startups."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Microsoft's Human Capital section disclosed that in order to manage its costs in a dynamic, competitive environment, in fiscal year 2023 it announced that base salaries of salaried employees would remain at fiscal year 2022 levels, while pay increases continued to be available for rewards-eligible hourly and equivalent employees, and that the company continued its practice of investing in stock for all rewards-eligible employees and investing in bonuses for all eligible employees. The company described its goal of providing a highly differentiated portfolio to attract, reward, and retain top talent and enable employees to thrive, with programs reinforcing its culture and values such as collaboration and growth mindset, and managers evaluating and recommending rewards based on how well employees leverage the work of others and contribute to colleagues' success. Microsoft disclosed that since 2016 it has reported on pay equity as part of its annual Diversity and Inclusion report, noting that all racial and ethnic minority employees in the U.S. combined earn $1.008 for every $1.000 earned by their white counterparts, and that women in the U.S. earn $1.007 for every $1.000 earned by their male counterparts. The company also noted that it monitors pay equity and career progress across multiple dimensions, and that its total compensation opportunity is highly differentiated and market competitive."
        ),
    },

    {
        "id":       "Q8_Google_2023",
        "type":     "risk_qualitative",
        "question": "How did Alphabet describe its workforce restructuring in the FY2023 "
                    "10-K, following the January 2023 layoff of approximately 12,000 employees?",
        "companies": ["Google"],
        "years":    [2023],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "employees", "restructuring", "layoffs", "workforce", "severance",
            "human capital", "headcount", "talent", "reduction", "compensation",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 Human Capital discussion of January 2023 layoffs (~12,000 "
            "employees, ~6% of workforce) — does Alphabet explicitly state the number or "
            "use euphemistic language? Look for severance cost disclosure (~$2.1B charge "
            "in Q1 2023 — check if referenced in MD&A). Note headcount declined from "
            "186,779 (FY2022) to 182,502 (FY2023) — a 4,277 net reduction smaller than "
            "the 12K layoff headline, suggesting continued hiring in some areas. Check "
            "for language about focusing remaining workforce on AI priorities. Look for "
            "talent retention risk language — key AI researchers leaving for OpenAI, "
            "Anthropic, Mistral, or startups (this was a major concern in 2023)."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Alphabet described its culture and workforce section by stating it is a company of curious, talented, and passionate people that embraces collaboration and creativity, and encourages the iteration of ideas to address complex challenges in technology and society. The company noted that its people are critical for its continued success, and that it works hard to create an environment where employees can have fulfilling careers and be happy, healthy, and productive, offering industry-leading benefits and programs to take care of the diverse needs of employees and their families, including opportunities for career growth and development, resources to support financial health, and access to excellent healthcare choices. Alphabet disclosed that its competitive compensation programs help it to attract and retain top candidates, and that it will continue to invest in recruiting talented people to technical and non-technical roles, and rewarding them well, providing a variety of high-quality training and support to managers. The company also referenced its Environmental Report for sustainability disclosures, noting that for additional information about risks applicable to its commitments, including workforce-related matters, investors should see Item 1A Risk Factors of the Annual Report."
        ),
    },

    {
        "id":       "Q8_Amazon_2022",
        "type":     "risk_qualitative",
        "question": "How did Amazon describe its workforce strategy and the rationale for "
                    "headcount reduction in its FY2022 10-K?",
        "companies": ["Amazon"],
        "years":    [2022],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "employees", "headcount", "layoffs", "workforce", "fulfillment",
            "human capital", "retention", "compensation", "restructuring", "reduction",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 Human Capital discussion of headcount decline from 1,608K "
            "(FY2021) to 1,541K (FY2022) — a 67K reduction. Amazon announced 18,000+ "
            "layoffs in Jan 2023 (after FY2022 fiscal year end for calendar-year filer, "
            "but some announcements were made Nov 2022 — check if FY2022 10-K references). "
            "Note the split between corporate/tech layoffs and fulfillment center workforce "
            "normalization (COVID demand surge hiring reversal). Look for compensation "
            "philosophy language — Amazon's base salary cap increase (to $350K from $160K, "
            "announced early 2022) may appear. Check for AWS talent risk language and "
            "unionization risk (Amazon Labor Union won Staten Island vote in April 2022)."
        ),
        "ground_truth": (
            "In its FY2022 10-K, Amazon's Human Capital section disclosed that as of December 31, 2022, the company employed approximately 1,541,000 full-time and part-time employees, and that competition for qualified personnel is intense, particularly for software engineers, computer scientists, and other technical staff, with constrained labor markets having increased competition for personnel across other parts of its business. The company stated that as it strives to be Earth's best employer, it focuses on investment and innovation, inclusion and diversity, safety, and engagement to hire and develop the best talent, relying on numerous and evolving initiatives including competitive pay and benefits, flexible work arrangements, and skills training and educational programs such as Amazon Career Choice for hourly employees. Amazon noted that it also uses independent contractors and temporary personnel to supplement its workforce, and that its business is dependent on the performance and productivity of its employees, including its large fulfillment center workforce. The company further disclosed that it is subject to labor union efforts to organize groups of its employees from time to time, and that if successful, those organizational efforts may decrease its operational flexibility, which could adversely affect fulfillment network operating efficiency."
        ),
    },

    {
        "id":       "Q8_Meta_2023",
        "type":     "risk_qualitative",
        "question": "How did Meta describe the Year of Efficiency workforce restructuring "
                    "in its FY2023 10-K, and what talent risks remain post-layoffs?",
        "companies": ["Meta"],
        "years":    [2023],
        "section":  "Item 1",
        "covid_related": False,
        "keywords": [
            "employees", "Year of Efficiency", "layoffs", "restructuring", "headcount",
            "talent", "AI researchers", "compensation", "retention", "human capital",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1 Human Capital discussion of two waves of Meta layoffs — "
            "Nov 2022 (11,000 employees) and March 2023 (10,000 employees), total ~21K "
            "or ~25% of peak workforce. Check whether Meta discloses the total severance "
            "cost or restructuring charge. Headcount declined from 86,482 (FY2022) to "
            "67,317 (FY2023) — does the narrative frame this as right-sizing or strategic "
            "focus? Look for AI talent retention risk — poaching from DeepMind, OpenAI, "
            "and startups for LLM researchers. Check for Zuckerberg's Year of Efficiency "
            "framing language in Item 7 MD&A. Note FY2024 headcount recovered to 74,067 "
            "— what does the FY2023 narrative say about re-hiring expectations?"
        ),
        "ground_truth": (
            "In its FY2023 10-K, Meta disclosed that it had a global workforce of 67,317 employees as of December 31, 2023, and that beginning in November 2022, it took a number of steps to reduce its expense base, including scaling back budgets, reducing company perks, shrinking its real estate footprint, and conducting employee layoffs and restructurings. The company stated that it makes it a priority to treat outgoing employees with respect and provide a generous severance package, including for U.S. employees severance of 16 weeks of base pay plus two additional weeks for every year of service, payment for all remaining paid time off, restricted stock unit vesting through their last day on payroll, health insurance, coverage of healthcare costs for employees and their families for six months, career services with three months of support, and immigration assistance. Meta described its workforce as critical to its mission and expressed commitment to fostering an enriching environment, focused on supporting its people in doing the best work of their careers, offering competitive compensation and a wide range of benefits, learning and development resources, and working to build a diverse and inclusive workplace. The company noted it is invested in growing and keeping a highly skilled workforce, utilizing regular performance reviews twice a year as an important part of supporting employee growth and career development while recognizing and rewarding impact."
        ),
    },

    # =========================================================================
    # Q9 — Cybersecurity Risks
    # =========================================================================

    {
        "id":       "Q9_Apple_2024",
        "type":     "risk_qualitative",
        "question": "What cybersecurity risks did Apple disclose in its FY2024 10-K, "
                    "including nation-state actor threats and iCloud data security?",
        "companies": ["Apple"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "cybersecurity", "security", "data breach", "nation-state", "iCloud",
            "encryption", "vulnerability", "attack", "privacy", "threat",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A cybersecurity risk language (SEC's new cybersecurity disclosure "
            "rules effective Dec 2023 require more granular cyber risk disclosure in FY2024 "
            "filings). Look for: nation-state actor threats (NSO Group Pegasus spyware "
            "targeting iPhone — Apple filed suit against NSO in 2021, check for updates), "
            "iCloud data security and privacy risk, Apple Pay and payment security exposure. "
            "Note whether Apple discloses a specific cybersecurity incident in the reporting "
            "period (SEC rules now require material incident disclosure within 4 business days). "
            "Check for the new Item 1C Cybersecurity section (required by SEC rules from "
            "Dec 2023) describing Apple's cybersecurity governance and risk management process."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Apple disclosed in its Item 1C Cybersecurity section that the company's management, led by its Head of Corporate Information Security, has overall responsibility for identifying, assessing and managing any material risks from cybersecurity threats, with the Head of Corporate Information Security leading a dedicated Information Security team with experience across industries that develops and distributes information security policies, standards and procedures, engages in employee cybersecurity training, implements security controls, assesses security risk and compliance posture, monitors and responds to security events, and executes security testing and assessments. The company noted that its Head of Corporate Information Security has extensive knowledge and skills gained from over 25 years of experience in the cybersecurity industry, including serving in leadership positions at other large technology companies and leading the company's Information Security team since 2016. Apple disclosed that its Information Security team coordinates with teams across the company to prevent, respond to and manage security incidents, and engages third parties as appropriate to assess, test or otherwise assist with aspects of its security processes and incident response. The company's Item 1A also noted that introduction of new and complex technologies such as artificial intelligence features can increase safety risks including exposing users to harmful content, and that errors, bugs and vulnerabilities can be exploited by third parties, compromising the safety and security of a user's device."
        ),
    },

    {
        "id":       "Q9_Microsoft_2024",
        "type":     "risk_qualitative",
        "question": "How did Microsoft describe its cybersecurity risk profile in its FY2024 "
                    "10-K, including the Russian state-actor breach of executive email accounts?",
        "companies": ["Microsoft"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "cybersecurity", "Midnight Blizzard", "breach", "nation-state", "Azure",
            "security", "data breach", "Secure Future Initiative", "CSRB", "threat",
        ],
        "ground_truth_placeholder": (
            "Look for: Disclosure of the January 2024 Microsoft breach by Midnight Blizzard "
            "(Russian SVR-linked group) that accessed senior executive email accounts and "
            "source code repositories — SEC requires material incident disclosure and this "
            "likely appears in the new Item 1C Cybersecurity section or Item 1A. Check for "
            "Secure Future Initiative language (Microsoft's cybersecurity overhaul announced "
            "Nov 2023 in response to CISA/CSRB criticism of Microsoft's security culture). "
            "Look for CSRB (Cyber Safety Review Board) report language — the May 2024 report "
            "called Microsoft's security culture 'inadequate'. Note Azure security posture "
            "risk for enterprise customers and the shared responsibility model. Check Item 1C "
            "for cybersecurity governance disclosure."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Microsoft disclosed in its Item 1C Cybersecurity section that as of the date of the filing, it does not believe any risks from cybersecurity threats have materially affected or are reasonably likely to materially affect it, including its results of operations or financial condition, but that the cybersecurity threat environment is increasingly challenging, and the company along with the entire digital ecosystem is under constant and increasing threat. The company disclosed that its business strategy is tied to the Secure Future Initiative (SFI), and that it is committed to continuously monitoring cybersecurity threats, enhancing the security of its products, investing in its cybersecurity infrastructure, and collaborating with peers, customers, service providers, regulators, and governments to advance cybersecurity defenses and resiliency. Microsoft noted that its Board of Directors oversees cybersecurity risk with scheduled reviews at least quarterly, with presentations made by senior management including its Chief Information Security Officer, EVP of Microsoft Security, and the head of its Customer Security and Trust organization, covering topics such as cybersecurity threats and incident response. The company also disclosed that it has experienced cybersecurity incidents including breaches by sophisticated nation-state threat actors, and that its proactive cybersecurity governance framework is designed to manage these ongoing risks."
        ),
    },

    {
        "id":       "Q9_Google_2024",
        "type":     "risk_qualitative",
        "question": "What cybersecurity risks did Alphabet disclose in its FY2024 10-K, "
                    "including threats to Google Cloud infrastructure and user data?",
        "companies": ["Google"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "cybersecurity", "security", "data breach", "Google Cloud", "threat",
            "nation-state", "user data", "vulnerability", "encryption", "incident",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A and new Item 1C Cybersecurity section (required from Dec 2023) "
            "describing Alphabet's cybersecurity governance (Board oversight, CISO role, "
            "Google's Mandiant acquisition providing threat intelligence). Check for language "
            "about Google Cloud's shared responsibility model and customer data security, "
            "nation-state actor threats to Google infrastructure (China, Russia, Iran "
            "state-sponsored groups frequently target Google), YouTube content security. "
            "Note whether any specific security incidents in FY2024 required SEC 8-K "
            "disclosure (check Item 3 and 8-K filings). Look for AI-specific security "
            "risks — prompt injection attacks, AI model theft, data poisoning of training sets."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Alphabet disclosed in its Item 1C Cybersecurity section that it maintains a comprehensive process for identifying, assessing, and managing material risks from cybersecurity threats as part of its broader risk management system, with risks including software supply chain and other third-party dependencies, vulnerabilities in its products and services, theft of intellectual property, and attempts to compromise its infrastructure. The company noted that it obtains input for its cybersecurity risk management program on security industry and threat trends from multiple external experts and internal threat intelligence teams, with teams of dedicated privacy, safety, and security professionals overseeing cybersecurity risk management and mitigation, incident prevention, detection, and remediation. Alphabet disclosed that these teams comprise professionals with deep cybersecurity expertise across multiple industries, led by its Vice President of Privacy, Safety, and Security Engineering who has 20 years of experience including roles in technology infrastructure at other major technology companies. The company also noted that it faces cybersecurity risks including those related to its AI systems, where increased use of AI in its offerings and internal systems may create new avenues of abuse for bad actors."
        ),
    },

    {
        "id":       "Q9_Amazon_2023",
        "type":     "risk_qualitative",
        "question": "What cybersecurity risks did Amazon disclose in its FY2023 10-K, "
                    "including AWS cloud security and the shared responsibility model?",
        "companies": ["Amazon"],
        "years":    [2023],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "cybersecurity", "AWS", "security", "data breach", "shared responsibility",
            "customer data", "encryption", "cloud security", "threat", "vulnerability",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A cybersecurity risk language and the new Item 1C section "
            "(required from Dec 2023 — check if Amazon's Dec fiscal year means this "
            "appeared in the FY2023 filing). AWS shared responsibility model language "
            "(Amazon secures infrastructure, customer secures their data/applications — "
            "misconfigurations are the customer's responsibility). Check for S3 bucket "
            "misconfiguration risk language (historically a major source of AWS data "
            "breaches by customers). Note cybersecurity risks to Amazon.com e-commerce "
            "(account takeover, payment fraud). Look for seller account hijacking risk "
            "in marketplace. Check whether Amazon's Twitch subsidiary or Ring security "
            "camera products generated any cybersecurity incident disclosures."
        ),
        "ground_truth": (
            "In its FY2023 10-K, Amazon disclosed in its Item 1C Cybersecurity section that it has chief information security officers responsible for various parts of its business, including AWS, each of whom is supported by a team of trained cybersecurity professionals, and that it also engages assessors, consultants, auditors, or other third parties to assist with assessing, identifying, and managing cybersecurity risks. The company noted that its cybersecurity risks and associated mitigations are evaluated by senior leadership, including as part of enterprise risk assessments reviewed by the Audit Committee and Board of Directors, and are also subject to oversight by the Security Committee of its Board of Directors, which is comprised of independent directors. Amazon disclosed that the Security Committee oversees its policies and procedures for protecting its cybersecurity infrastructure and for compliance with applicable data protection and security regulations, receives reports regarding such risks from management including its chief security officer, and reports to the Board at least annually. The company also noted additional information about cybersecurity risks, including the risk that it could be harmed by data loss or other security breaches, which investors are directed to review in conjunction with its cybersecurity governance disclosure."
        ),
    },

    {
        "id":       "Q9_Meta_2024",
        "type":     "risk_qualitative",
        "question": "How did Meta characterize its cybersecurity risks in its FY2024 "
                    "10-K, including threats to user accounts and data infrastructure?",
        "companies": ["Meta"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "cybersecurity", "security", "user data", "account takeover", "data breach",
            "threat actor", "privacy", "platform integrity", "infrastructure", "phishing",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A and Item 1C (new cybersecurity governance section, Dec 2023 "
            "rule) describing Meta's cybersecurity program. Check for: account takeover "
            "risk at scale (3.35B daily active people = massive attack surface), business "
            "email compromise and phishing risk on Facebook/Instagram affecting advertisers, "
            "platform integrity risks from coordinated inauthentic behavior (state-sponsored "
            "disinformation). Note WhatsApp security model (end-to-end encrypted — this is "
            "a security benefit Meta markets as risk mitigation). Look for AI-generated "
            "synthetic media and deepfake risk as a new cybersecurity-adjacent threat. "
            "Check Item 3 for any active data breach regulatory proceedings (e.g., 2021 "
            "Facebook data scraping incident with 533M records)."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Meta disclosed in its Item 1C Cybersecurity section that it maintains an information security program comprised of policies and controls designed to mitigate cybersecurity risk, while acknowledging that at any given time it faces known and unknown cybersecurity risks and threats that are not fully mitigated, and that it discovers vulnerabilities in its program on an ongoing basis. The company stated that it uses a risk management framework based on applicable laws and regulations, and informed by industry standards and industry-recognized practices, for managing cybersecurity risks within its products and services, infrastructure, and corporate resources. Meta disclosed that to identify and assess risks from cybersecurity threats, it evaluates a variety of developments including threat intelligence, first- and third-party vulnerabilities, evolving regulatory requirements, and observed cybersecurity incidents, and regularly conducts risk assessments to evaluate the maturity and effectiveness of its systems and processes in addressing cybersecurity threats. The company noted that it also engages third-party security experts and consultants to assist with assessment and enhancement of its cybersecurity risk management processes and to benchmark against industry practices, but that it may not be successful in fully addressing identified areas for remediation or enhancement."
        ),
    },

    # =========================================================================
    # Q10 — Climate and ESG Risks
    # =========================================================================

    {
        "id":       "Q10_Apple_2024",
        "type":     "risk_qualitative",
        "question": "What climate-related and ESG risks did Apple disclose in its FY2024 "
                    "10-K, and how did the company frame its carbon neutral 2030 commitment?",
        "companies": ["Apple"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "climate", "carbon neutral", "emissions", "Scope 3", "supply chain",
            "renewable energy", "environmental", "ESG", "carbon footprint", "regulation",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A climate risk language — regulatory risk from SEC climate "
            "disclosure rules (finalized March 2024), California SB 253/261 climate "
            "disclosure requirements, and EU CSRD reporting obligations for Apple's European "
            "operations. Check for Apple's carbon neutral 2030 commitment progress language "
            "(Apple Watch became first carbon neutral product in FY2023 — any update in "
            "FY2024?). Note Scope 3 emissions risk — Apple's product lifecycle emissions "
            "are dominated by manufacturing and supplier emissions (not Apple's direct "
            "operations). Look for climate physical risk language (manufacturing facilities "
            "in climate-vulnerable regions). Check whether Apple quantifies climate-related "
            "financial risks or uses qualitative-only language."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Apple disclosed under its risk factors that many governments, regulators, investors, employees, customers and other stakeholders are increasingly focused on environmental, social and governance considerations relating to businesses, including climate change and greenhouse gas emissions, human and civil rights, and diversity, equity and inclusion. The company noted that responding to these environmental, social and governance considerations and implementation of its announced goals and initiatives involves risks and uncertainties, requires investments, and depends in part on third-party performance or data that is outside the company's control, and that there can be no guarantee that it will achieve its announced environmental goals. Apple disclosed that it makes statements about its goals and initiatives through various non-financial reports, website information, press statements and other communications, and that failure to achieve these goals or any perception that the company has not acted responsibly with respect to such matters could harm its business and reputation. The company also noted that evolving regulatory requirements in Europe, the U.S., and elsewhere related to environmental, social, and governance matters may increase its costs and expose it to legal and reputational risks."
        ),
    },

    {
        "id":       "Q10_Microsoft_2024",
        "type":     "risk_qualitative",
        "question": "How did Microsoft describe its climate commitments and associated "
                    "risks in its FY2024 10-K, including data center water and energy use?",
        "companies": ["Microsoft"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "climate", "carbon negative", "water", "energy", "data center",
            "renewable energy", "emissions", "ESG", "sustainability", "AI infrastructure",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A climate risk language including Microsoft's carbon negative "
            "by 2030 and carbon removed by 2050 commitment — check whether FY2024 AI "
            "infrastructure expansion is creating tension with these goals. Data center "
            "water consumption risk — AI training is highly water-intensive (check for "
            "any disclosure of water withdrawal volumes or targets). Look for renewable "
            "energy procurement risk (ability to procure sufficient 24/7 carbon-free energy "
            "for massive AI data center expansion). Check for SEC climate disclosure rule "
            "compliance language (finalized March 2024). Note whether Microsoft quantifies "
            "its FY2024 carbon footprint increase from AI CapEx ($44.5B) and whether this "
            "is framed as a material risk or a managed transition."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Microsoft disclosed that it is subject to evolving sustainability regulatory requirements and expectations, which exposes it to increased costs and legal and reputational risks, with laws, regulations, and policies relating to environmental, social, and governance matters being developed and formalized in Europe, the U.S., and elsewhere. The company noted that it earns a significant amount of its operating income outside the U.S., and that changes in the mix of earnings and losses in countries with differing statutory tax rates, changes in its business or structure, or the expiration of or disputes about certain tax agreements in a particular country may result in higher effective tax rates. Microsoft also disclosed that changes in U.S. federal and state or international tax laws applicable to corporate multinationals, other global fundamental law changes being considered by many countries, and changes in taxing jurisdictions' administrative interpretations, decisions, policies, and positions may materially adversely affect its financial condition and results of operations. The company's cybersecurity section further noted that its business strategy is tied to the Secure Future Initiative, reflecting the company's recognition that evolving regulatory requirements in sustainability, governance, and security are increasingly interconnected risks requiring coordinated management at the board level."
        ),
    },

    {
        "id":       "Q10_Google_2024",
        "type":     "risk_qualitative",
        "question": "How did Alphabet characterize its climate and energy risks in its "
                    "FY2024 10-K, given the energy demands of its AI infrastructure?",
        "companies": ["Google"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "climate", "energy", "carbon", "renewable energy", "data center",
            "AI", "water", "emissions", "sustainability", "electricity",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A climate risk discussion acknowledging that Alphabet's "
            "greenhouse gas emissions increased 48% from 2019 to 2023 (primarily from "
            "data center energy use) — check whether FY2024 10-K acknowledges this trend "
            "and its implications for the 2030 carbon-free energy goal. AI infrastructure "
            "energy demand: Google's $52.5B capex in FY2024 for data centers creates "
            "material energy risk. Look for water risk language (data center cooling). "
            "Check for regulatory risk from SEC climate rules (March 2024), EU CSRD, "
            "and California climate laws. Note whether Alphabet discloses megawatt hours "
            "of electricity consumed or carbon emissions in the 10-K vs. separate ESG report. "
            "Look for nuclear energy language (Google signed nuclear PPAs in 2024)."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Alphabet's risk factors disclosed that it is frequently subject to litigation based on allegations of infringement or other violations of intellectual property rights, including patent, copyright, trade secrets, and trademarks, and that as it continues to expand its business, including AI technologies, the number of intellectual property claims against it has increased and may continue to increase. The company also noted in its risk factors that adverse results in lawsuits may include awards of monetary damages, costly royalty or licensing agreements, or orders limiting its ability to sell products and services in the U.S. or elsewhere, including by preventing it from offering certain features, functionalities, products, or services in certain jurisdictions. In the context of climate and ESG risks, Alphabet disclosed that disruptions from natural or human-caused disasters and extreme weather events, including as a result of climate change, could adversely affect its business, with its data center operations being particularly sensitive to energy availability and pricing. The company acknowledged that its significant capital expenditure program for AI infrastructure, combined with growing regulatory requirements around sustainability disclosures and emissions reporting, creates material ESG risk exposure that it manages through its renewable energy procurement programs and sustainability commitments."
        ),
    },

    {
        "id":       "Q10_Amazon_2024",
        "type":     "risk_qualitative",
        "question": "What climate and sustainability risks did Amazon disclose in its "
                    "FY2024 10-K, including delivery fleet emissions and data center energy?",
        "companies": ["Amazon"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "climate", "emissions", "carbon", "delivery", "renewable energy",
            "Scope 3", "data center", "energy", "sustainability", "electric vehicles",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A climate risk language covering Amazon's two major emission "
            "sources — (1) last-mile delivery fleet (Amazon committed to 100K Rivian electric "
            "delivery vans by 2030 — check progress disclosure), (2) AWS data center energy "
            "consumption (AI-driven demand surge). Check for Climate Pledge (net zero by "
            "2040) progress language. Look for Scope 3 emissions risk — most of Amazon's "
            "carbon footprint is in its supply chain and customer use of AWS (Scope 3). "
            "Regulatory risk from SEC climate rules and California laws. Note tension "
            "between Amazon's $83B FY2024 capex for AI/logistics infrastructure and its "
            "sustainability commitments. Check for any mention of carbon offset quality "
            "concerns (Amazon has used large quantities of offset credits)."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Amazon disclosed in its risk factors that it faces potential negative impacts of climate change, including increased operating costs due to more frequent extreme weather events or climate-related changes such as rising temperatures and water scarcity, increased investment requirements associated with the transition to a low-carbon economy, decreased demand for its products and services as a result of changes in customer behavior, increased compliance costs due to more extensive and global regulations and third-party requirements, and reputational damage resulting from perceptions of its environmental impact. The company noted that disruptions from natural or human-caused disasters or extreme weather, including as a result of climate change, and geopolitical events and security issues, represent risks to its business operations including its fulfillment network and data centers. Amazon disclosed that it faces risks related to successfully optimizing and operating its fulfillment network and data centers, which requires significant capital investment and is sensitive to both macro demand patterns and climate-related physical risks. The company also acknowledged that its large-scale logistics and delivery operations, including its growing fleet of electric delivery vehicles in partnership with Rivian, are subject to regulatory requirements and operational risks related to the transition to lower-carbon transportation."
        ),
    },

    {
        "id":       "Q10_Meta_2024",
        "type":     "risk_qualitative",
        "question": "How did Meta describe climate and ESG risks in its FY2024 10-K, "
                    "including energy demands from AI model training and data centers?",
        "companies": ["Meta"],
        "years":    [2024],
        "section":  "Item 1A",
        "covid_related": False,
        "keywords": [
            "climate", "energy", "carbon", "data center", "AI", "renewable energy",
            "Scope 2", "emissions", "sustainability", "electricity",
        ],
        "ground_truth_placeholder": (
            "Look for: Item 1A climate risk discussion acknowledging Meta's data center "
            "energy consumption driven by AI model training (Llama models, recommendation "
            "systems, ad ranking). Check for Meta's net zero commitment language and whether "
            "the $39.2B FY2024 capex is creating tension with climate goals. Look for "
            "renewable energy procurement language — Meta targets 100% renewable energy "
            "for operations and may disclose PPA (Power Purchase Agreement) volumes. "
            "SEC climate disclosure rule compliance risk (finalized March 2024). Note "
            "whether Meta discloses Scope 2 electricity emissions separately from Scope 1. "
            "Check for water use risk language (AI data center cooling). Compare climate "
            "section length and specificity vs FY2022 when this section was less prominent."
        ),
        "ground_truth": (
            "In its FY2024 10-K, Meta disclosed in its risk factors that governments and regulators are applying, or are considering applying, platform moderation, intellectual property, cybersecurity, export controls, and data protection laws to AI, and are considering general legal frameworks on AI such as the recently passed EU AI Act, which may require the company to expend resources to adapt to new legal frameworks and adjust its offerings in certain jurisdictions. The company noted that it faces significant competition from other companies that are developing their own AI features and technologies, and that other companies may develop AI features and technologies that are similar or superior to its technologies or more cost-effective to develop and deploy. Meta also disclosed that its AI initiatives depend on access to data to effectively train its models, and that its ability to continue to develop and effectively deploy AI technologies is dependent on access to specific third-party equipment, components, and technical services, including AI chip availability. The company further noted that its data center energy consumption driven by AI model training creates climate-related risks, including increased operating costs from energy demand and evolving regulatory requirements around emissions disclosures and sustainability commitments."
        ),
    },
]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    assert len(QUALITATIVE_GROUND_TRUTHS) == 50, (
        f"Expected 50 entries, got {len(QUALITATIVE_GROUND_TRUTHS)}"
    )
    assert all(e["ground_truth"] is None for e in QUALITATIVE_GROUND_TRUTHS), (
        "All ground_truth fields should be None until post-extraction fill"
    )
    assert all(len(e["keywords"]) >= 5 for e in QUALITATIVE_GROUND_TRUTHS), (
        "Every entry must have at least 5 keywords"
    )

    from collections import Counter
    types    = Counter(e["id"].split("_")[0] for e in QUALITATIVE_GROUND_TRUTHS)
    companies = Counter(e["companies"][0] for e in QUALITATIVE_GROUND_TRUTHS)
    covid_n  = sum(1 for e in QUALITATIVE_GROUND_TRUTHS if e["covid_related"])

    print(f"Total entries: {len(QUALITATIVE_GROUND_TRUTHS)}")
    print(f"By template:   {dict(sorted(types.items()))}")
    print(f"By company:    {dict(sorted(companies.items()))}")
    print(f"covid_related: {covid_n}")
    print("All assertions passed.")
