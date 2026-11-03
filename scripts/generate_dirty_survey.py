#!/usr/bin/env python3
"""Synthetic Messy Survey Data Generator.

==============================================================================
DISCLAIMER: CLEARLY LABELLED SYNTHETIC DATA
This script generates purely SYNTHETIC data designed specifically for testing
data engineering pipelines, data quality rules, and cleaning algorithms.
It does NOT contain real survey responses and must NOT be represented as real.
==============================================================================
"""

import argparse
import random
from pathlib import Path
from typing import List, Tuple
import numpy as np
import pandas as pd

# Reproducible random seed
SEED = 42

# Realistic raw domain lists with messy variants
RAW_STATES = [
    ("Uttar Pradesh", ["UP", "U.P.", "uttar pradesh", "utar pradesh", " U.P "]),
    ("Maharashtra", ["MH", "M.H.", "maharashtra", "Maharastra", "mh"]),
    ("Karnataka", ["KA", "karnataka", "Karnatak", "k.a.", "Karnataka "]),
    ("Tamil Nadu", ["TN", "tamilnadu", "Tamil Nadu", "T.N.", "tamil nadu"]),
    ("Delhi", ["DL", "delhi", "New Delhi", "D.L.", " delhi"]),
    ("West Bengal", ["WB", "west bengal", "West Bangal", "w.b.", "WB "]),
    ("Rajasthan", ["RJ", "rajasthan", "Rajastan", "rj"]),
    ("Gujarat", ["GJ", "gujarat", "GIllarat", "gujarath", "GJ"]),
    ("Bihar", ["BR", "bihar", "Bihar ", "br"]),
    ("Madhya Pradesh", ["MP", "madhya pradesh", "M.P.", "mp"]),
    ("Kerala", ["KL", "kerala", "Kerala", "kl"]),
    ("Punjab", ["PB", "punjab", "PB", "pb"]),
]

DISTRICTS = {
    "Uttar Pradesh": ["Lucknow", "Varanasi", "Kanpur", "Agra", "Prayagraj"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane"],
    "Karnataka": ["Bengaluru Urban", "Mysuru", "Hubballi", "Mangaluru"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli"],
    "Delhi": ["Central Delhi", "South Delhi", "North Delhi", "East Delhi"],
    "West Bengal": ["Kolkata", "Howrah", "Darjeeling", "Siliguri"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Gwalior", "Jabalpur"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala"],
}

GENDERS = ["Male", "Female", "Non-Binary", "Prefer not to say"]
GENDER_MESSY = ["M", "F", "male", "FEMALE", "m", "f", ""]

OCCUPATIONS = [
    "Software Engineer", "Data Scientist", "Student", "Teacher",
    "Government Employee", "Business Owner", "Farmer", "Homemaker",
    "Unemployed", "Doctor", "Lawyer", "Sales Executive",
]
OCCUPATION_MESSY = [
    "developer", "studying", "govt employee", "businessman", "kisan",
    "housewife", "sw engineer", "civil servant", "shopkeeper",
]

EDUCATIONS = [
    "High School", "Senior Secondary", "Bachelor's Degree",
    "Master's Degree", "Doctorate (Ph.D.)", "Diploma",
]
EDUCATION_MESSY = [
    "10th pass", "12th pass", "btech", "b.com", "m.tech", "mba",
    "undergraduate", "phd", "college grad",
]

PARTIES = [
    ("Bharatiya Janata Party", ["BJP", "B.J.P.", "bharatiya janata party", "bhartiya janata party"]),
    ("Indian National Congress", ["INC", "congress", "I.N.C.", "indian national congress"]),
    ("Aam Aadmi Party", ["AAP", "aam aadmi party", "A.A.P."]),
    ("Trinamool Congress", ["TMC", "all india trinamool congress", "aitc"]),
    ("Samajwadi Party", ["SP", "samajwadi party"]),
    ("Independent", ["IND", "independent", "ind"]),
    ("None / Undecided", ["None", "undecided", "NOTA", "nota"]),
]

MULTI_SELECT_ISSUES = [
    "Inflation", "Unemployment", "Healthcare Access", "Road Infrastructure",
    "Education Quality", "Corruption", "Water Supply", "Air Pollution",
    "Digital Connectivity", "Agricultural MSP",
]

COMMENTS = [
    "Very satisfied with the public transport infrastructure improvement.",
    "Inflation is hitting daily household budgets severely.",
    "Road quality in our district needs immediate attention.",
    "Appreciate the digital governance services and fast certificate issuance.",
    "Healthcare facilities in rural areas require more qualified doctors.",
    "Youth employment opportunities must be created urgently.",
    "Drinking water supply is irregular during summer months.",
    "Education infrastructure has seen good upgrades in government schools.",
    "Local administration is responsive to citizen complaints.",
    "Need more focus on pollution control and green cover in city.",
]

MOJIBAKE_SAMPLES = [
    "CafÃ© owner near station",
    "Dr. MÃ¼ller clinic visit",
    "NaÃ¯ve expectations from council",
    "FaÃ§ade of local building",
    "RÃ©sumÃ© submitted for govt job",
]

MISSING_TOKENS = ["N/A", "NA", "-", "none", "", "NaN", "null", "NULL", "   ", "Not Available"]


def generate_dirty_survey(num_rows: int = 10000, seed: int = SEED) -> pd.DataFrame:
    """Generates synthetic survey responses with deliberate, realistic anomalies."""
    random.seed(seed)
    np.random.seed(seed)

    records = []
    # Base respondent IDs
    unique_ids = [f"RESP_{i:07d}" for i in range(1, int(num_rows * 0.95) + 1)]

    for i in range(num_rows):
        # 1. Respondent ID (inject ~5% duplicate IDs)
        if i < len(unique_ids):
            resp_id = unique_ids[i]
        else:
            resp_id = random.choice(unique_ids[:1000])  # Duplicate existing

        # 2. State & District
        state_tuple = random.choice(RAW_STATES)
        canonical_state, messy_variants = state_tuple
        state_val = canonical_state if random.random() > 0.35 else random.choice(messy_variants)
        district_list = DISTRICTS.get(canonical_state, ["Central"])
        district_val = random.choice(district_list)

        # 3. Age (inject ~4% outliers: negative, zero, or > 120)
        age_rand = random.random()
        if age_rand < 0.02:
            age_val = random.choice([-5, -1, 0, 180, 250])  # Invalid outlier
        elif age_rand < 0.06:
            age_val = random.choice(MISSING_TOKENS)  # Missing
        else:
            age_val = int(np.random.normal(38, 14))
            age_val = max(18, min(85, age_val))

        # 4. Gender
        if random.random() < 0.15:
            gender_val = random.choice(GENDER_MESSY)
        else:
            gender_val = random.choice(GENDERS)

        # 5. Education
        if random.random() < 0.20:
            education_val = random.choice(EDUCATION_MESSY)
        elif random.random() < 0.05:
            education_val = random.choice(MISSING_TOKENS)
        else:
            education_val = random.choice(EDUCATIONS)

        # 6. Occupation
        if random.random() < 0.20:
            occupation_val = random.choice(OCCUPATION_MESSY)
        elif random.random() < 0.05:
            occupation_val = random.choice(MISSING_TOKENS)
        else:
            occupation_val = random.choice(OCCUPATIONS)

        # 7. Monthly Income (inject ~3% outliers and messy formatting)
        inc_rand = random.random()
        if inc_rand < 0.02:
            income_val = random.choice([-10000, 25000000, 99999999])  # Severe outliers
        elif inc_rand < 0.08:
            income_val = random.choice(MISSING_TOKENS)
        else:
            base_income = int(np.random.lognormal(mean=10.4, sigma=0.6))
            fmt_choice = random.random()
            if fmt_choice < 0.20:
                income_val = f"₹ {base_income:,}"
            elif fmt_choice < 0.35:
                income_val = f"{base_income:,.2f}"
            elif fmt_choice < 0.45:
                income_val = f" ${base_income // 83} "
            else:
                income_val = str(base_income)

        # 8. Party Preference
        party_tuple = random.choice(PARTIES)
        canonical_party, party_variants = party_tuple
        if random.random() < 0.35:
            party_val = random.choice(party_variants)
        elif random.random() < 0.05:
            party_val = random.choice(MISSING_TOKENS)
        else:
            party_val = canonical_party

        # 9. Rating 1 to 5
        rating_rand = random.random()
        if rating_rand < 0.03:
            rating_val = random.choice([-1, 0, 6, 10, 99])  # Invalid rating
        elif rating_rand < 0.08:
            rating_val = random.choice(MISSING_TOKENS)
        else:
            rating_val = random.choices([1, 2, 3, 4, 5], weights=[0.1, 0.15, 0.3, 0.3, 0.15])[0]

        # 10. Response Date (mixed formats)
        year = random.choice([2024, 2025])
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        date_fmt = random.random()
        if date_fmt < 0.40:
            date_val = f"{year:04d}-{month:02d}-{day:02d}"  # ISO
        elif date_fmt < 0.65:
            date_val = f"{day:02d}/{month:02d}/{year:04d}"  # DD/MM/YYYY
        elif date_fmt < 0.85:
            date_val = f"{month:02d}-{day:02d}-{year:04d}"  # MM-DD-YYYY
        elif date_fmt < 0.95:
            date_val = f"{year:04d}/{month:02d}/{day:02d}"
        else:
            date_val = random.choice(MISSING_TOKENS)

        # 11. Multi-Select Choices (semicolon separated)
        num_choices = random.randint(1, 4)
        selected_issues = random.sample(MULTI_SELECT_ISSUES, num_choices)
        choices_val = ";".join(selected_issues)
        if random.random() < 0.10:
            choices_val += "; "  # Stray trailing delimiter

        # 12. Free-text comment with occasional mojibake / whitespace
        comment_rand = random.random()
        if comment_rand < 0.05:
            comment_val = random.choice(MOJIBAKE_SAMPLES)
        elif comment_rand < 0.15:
            comment_val = random.choice(MISSING_TOKENS)
        else:
            comment_val = random.choice(COMMENTS)
            if random.random() < 0.20:
                comment_val = f"  {comment_val}   "  # Stray padding

        records.append({
            "respondent_id": resp_id,
            "state": state_val,
            "district": district_val,
            "age": age_val,
            "gender": gender_val,
            "education": education_val,
            "occupation": occupation_val,
            "monthly_income": income_val,
            "party_preference": party_val,
            "rating_1_to_5": rating_val,
            "response_date": date_val,
            "multi_select_choices": choices_val,
            "free_text_comment": comment_val,
            "data_classification": "SYNTHETIC_TEST_DATA",
        })

    df = pd.DataFrame(records)
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic dirty survey dataset with deliberate real-world flaws."
    )
    parser.add_argument("--rows", type=int, default=10000, help="Number of rows to generate (default: 10000)")
    parser.add_argument("--output", type=str, default="data/sample/survey_sample_dirty.csv", help="Output CSV path")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed for reproducibility")
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Generating {args.rows} synthetic survey rows with seed={args.seed}...")
    df = generate_dirty_survey(num_rows=args.rows, seed=args.seed)
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"[SUCCESS] Synthetic dirty survey dataset saved to: {out_path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
