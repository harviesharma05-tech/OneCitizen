"""Government scheme catalogue.

Includes several deliberately overlapping schemes across departments — the
duplicate-scheme detector should surface them without being told.
"""

SCHEMES = [
    {
        "name": "PM-Kisan Samman Nidhi",
        "department": "Agriculture",
        "objective": "Income support to small and marginal farmer families holding cultivable land",
        "eligibility": "Applicant must be a farmer with landholding below 2.0 hectares and annual income below 200000",
        "benefit": "₹6,000 per year in three instalments",
    },
    {
        "name": "Krishi Sinchai Yojana",
        "department": "Agriculture",
        "objective": "Irrigation and water access support for cultivating farmers",
        "eligibility": "Applicant must be a farmer with landholding below 4.0 hectares",
        "benefit": "Up to ₹50,000 irrigation subsidy",
    },
    {
        "name": "Kisan Credit Support",
        "department": "Agriculture",
        "objective": "Income assistance for small and marginal farmer households with cultivable land",
        "eligibility": "Applicant must be a farmer with landholding below 2.0 hectares and annual income below 200000",
        "benefit": "Subsidised credit up to ₹1,00,000",
    },
    {
        "name": "PM Awas Yojana (Gramin)",
        "department": "Housing",
        "objective": "Pucca housing for rural households without adequate shelter",
        "eligibility": "Annual income below 180000 and applicant age above 21",
        "benefit": "₹1,20,000 construction assistance",
    },
    {
        "name": "State Housing Subsidy",
        "department": "Housing",
        "objective": "Housing construction assistance for rural families lacking permanent shelter",
        "eligibility": "Annual income below 180000 and applicant age above 21",
        "benefit": "₹90,000 subsidy",
    },
    {
        "name": "Rural Shelter Grant",
        "department": "RuralDev",
        "objective": "Grant for shelter construction among low income rural households",
        "eligibility": "Annual income below 150000 and age above 25",
        "benefit": "₹75,000 one-time grant",
    },
    {
        "name": "Old Age Pension",
        "department": "SocialWelfare",
        "objective": "Monthly pension for elderly citizens with no stable income source",
        "eligibility": "Age above 60 and annual income below 120000",
        "benefit": "₹1,200 per month",
    },
    {
        "name": "Widow Pension Scheme",
        "department": "SocialWelfare",
        "objective": "Monthly financial support for widowed women with low household income",
        "eligibility": "Applicant is a widow, female, age above 40 and annual income below 120000",
        "benefit": "₹1,000 per month",
    },
    {
        "name": "Disability Support Allowance",
        "department": "SocialWelfare",
        "objective": "Monthly allowance for persons with disability requiring assistance",
        "eligibility": "Annual income below 150000 and age above 18",
        "benefit": "₹1,500 per month",
    },
    {
        "name": "Post-Matric Scholarship",
        "department": "Education",
        "objective": "Tuition and maintenance support for students continuing after class 10",
        "eligibility": "Applicant must be a student with education 12th or higher and annual income below 250000",
        "benefit": "₹25,000 per academic year",
    },
    {
        "name": "Merit Scholarship for PG",
        "department": "Education",
        "objective": "Financial assistance for postgraduate students from low income families",
        "eligibility": "Applicant must be a student with postgraduate education and annual income below 250000",
        "benefit": "₹40,000 per academic year",
    },
    {
        "name": "Skill Training Stipend",
        "department": "Education",
        "objective": "Stipend for unemployed youth enrolled in vocational skill training",
        "eligibility": "Applicant must be unemployed, age below 35 and annual income below 200000",
        "benefit": "₹8,000 training stipend",
    },
    {
        "name": "MGNREGA Wage Support",
        "department": "RuralDev",
        "objective": "Guaranteed wage employment for rural households seeking manual work",
        "eligibility": "Applicant must be a labourer, age above 18 and annual income below 200000",
        "benefit": "100 days guaranteed wage employment",
    },
    {
        "name": "Rural Livelihood Mission",
        "department": "RuralDev",
        "objective": "Livelihood and self employment support for rural women in low income households",
        "eligibility": "Applicant is female, age above 18 and annual income below 200000",
        "benefit": "₹30,000 livelihood grant",
    },
    {
        "name": "Village Infra Grant",
        "department": "RuralDev",
        "objective": "Community infrastructure funding at village panchayat level",
        "eligibility": "Applicant age above 21",
        "benefit": "Panchayat-level grant",
    },
]
