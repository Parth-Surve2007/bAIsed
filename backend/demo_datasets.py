import pandas as pd
import numpy as np
from io import StringIO

def generate_credit_demo(n_samples=2000):
    np.random.seed(42)
    # Protected: Age Category (Young/Senior vs Adult)
    # Outcome: Loan Approved
    
    age = np.random.choice(["Young (<25)", "Adult (25-60)", "Senior (>60)"], n_samples, p=[0.2, 0.6, 0.2])
    income = np.random.normal(60000, 20000, n_samples)
    income = np.clip(income, 20000, 200000)
    
    # Introduce bias: Young and Senior have lower income on average
    income[age == "Young (<25)"] -= 15000
    income[age == "Senior (>60)"] -= 10000
    
    # Proxy: Zip Code (correlated with age/income)
    zip_code = np.where(income > 70000, "Zone A", np.where(income > 40000, "Zone B", "Zone C"))
    
    # Outcome logic
    base_score = income / 1000 - 30
    
    # Direct bias against Young
    base_score[age == "Young (<25)"] -= 15
    
    prob = 1 / (1 + np.exp(-base_score / 15))
    approved = (np.random.rand(n_samples) < prob).astype(int)
    
    df = pd.DataFrame({
        "Age Category": age,
        "Annual Income": np.round(income, 2),
        "Zip Code Zone": zip_code,
        "Employment Status": np.random.choice(["Employed", "Self-Employed", "Unemployed"], n_samples, p=[0.7, 0.2, 0.1]),
        "Loan Approved": approved
    })
    return df

def generate_resume_demo(n_samples=2000):
    np.random.seed(42)
    # Protected: Gender
    # Outcome: Interview Callback
    
    gender = np.random.choice(["Male", "Female", "Non-Binary"], n_samples, p=[0.48, 0.48, 0.04])
    gpa = np.random.normal(3.2, 0.4, n_samples)
    gpa = np.clip(gpa, 2.0, 4.0)
    
    # Men get slightly higher "perceived" experience due to bias
    experience_years = np.random.poisson(5, n_samples)
    experience_years[gender == "Male"] += 1
    
    # Proxy: Tech Club Membership
    tech_club = np.where((gender == "Male") | (gpa > 3.7), "Yes", "No")
    
    # Outcome logic
    score = gpa * 10 + experience_years * 2
    # Bias: Tech club membership highly weighted
    score[tech_club == "Yes"] += 15
    
    # Direct penalty
    score[gender == "Female"] -= 5
    
    prob = 1 / (1 + np.exp(-(score - 40) / 10))
    callback = (np.random.rand(n_samples) < prob).astype(int)
    
    df = pd.DataFrame({
        "Gender": gender,
        "College GPA": np.round(gpa, 2),
        "Years Experience": experience_years,
        "Tech Club Member": tech_club,
        "Interview Callback": callback
    })
    return df

def generate_policing_demo(n_samples=2000):
    np.random.seed(42)
    # Protected: Race
    # Outcome: Arrested
    
    race = np.random.choice(["Majority", "Minority A", "Minority B"], n_samples, p=[0.6, 0.3, 0.1])
    
    # Proxy: Neighborhood
    neighborhood = np.where(race == "Majority", 
                            np.random.choice(["North", "West", "East"], len(race)),
                            np.random.choice(["South", "East"], len(race)))
    
    # Previous incidents
    priors = np.random.poisson(1, n_samples)
    # Over-policing in South neighborhood
    priors[neighborhood == "South"] += 2
    
    score = priors * 5
    # Direct bias based on neighborhood 
    score[neighborhood == "South"] += 10
    
    prob = 1 / (1 + np.exp(-(score - 10) / 5))
    arrested = (np.random.rand(n_samples) < prob).astype(int)
    
    df = pd.DataFrame({
        "Race": race,
        "Neighborhood": neighborhood,
        "Prior Incidents": priors,
        "Arrested": arrested
    })
    return df

def generate_demo_csv(demo_type):
    if demo_type == "credit":
        df = generate_credit_demo()
    elif demo_type == "resume":
        df = generate_resume_demo()
    elif demo_type == "policing":
        df = generate_policing_demo()
    else:
        raise ValueError(f"Unknown demo type: {demo_type}")
    
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()
