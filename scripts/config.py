"""
config.py — Shared constants and reference data for the data generation pipeline.

This module is the SINGLE SOURCE OF TRUTH for all configuration values used
across the six generator modules. Every distribution, lookup table, and
threshold is defined here so that:
  1. Changes propagate to all modules automatically.
  2. The generation logic in each module stays focused on its own table.
  3. Auditors can review all assumptions in one place.

Currency: INR (₹) throughout.
Seed: 42 for full reproducibility.
"""

import os
from datetime import date

# ============================================================================
# REPRODUCIBILITY
# ============================================================================
RANDOM_SEED = 42

# ============================================================================
# DATE RANGE
# ============================================================================
DATA_START = date(2024, 1, 1)
DATA_END   = date(2025, 12, 31)

# Signups stop 3 months before DATA_END so that every cohort has at least
# one quarter of potential order activity for retention analysis.
SIGNUP_END = date(2025, 9, 30)

# ============================================================================
# OUTPUT PATHS
# ============================================================================
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "raw")

# ============================================================================
# VOLUME TARGETS
# ============================================================================
TARGET_CUSTOMERS       = 20_000
TARGET_ORDERS          = 60_000
TARGET_ORDER_ITEMS_MIN = 150_000

# ============================================================================
# CATEGORIES — 14 rows (hardcoded lookup)
# ============================================================================
# (category_id, category_name, sub_category)
CATEGORIES = [
    (1,  "Electronics",       "Smartphones"),
    (2,  "Electronics",       "Laptops"),
    (3,  "Electronics",       "Headphones"),
    (4,  "Clothing",          "Men's Wear"),
    (5,  "Clothing",          "Women's Wear"),
    (6,  "Clothing",          "Footwear"),
    (7,  "Home & Kitchen",    "Cookware"),
    (8,  "Home & Kitchen",    "Furniture"),
    (9,  "Sports & Outdoors", "Fitness Equipment"),
    (10, "Sports & Outdoors", "Camping Gear"),
    (11, "Books",             "Fiction"),
    (12, "Books",             "Non-Fiction"),
    (13, "Beauty & Health",   "Skincare"),
    (14, "Beauty & Health",   "Supplements"),
]

# Number of products to generate per subcategory (sums to 500)
PRODUCTS_PER_SUBCATEGORY = {
    1: 40,  2: 20,  3: 30,   # Electronics  → 90
    4: 45,  5: 45,  6: 30,   # Clothing     → 120
    7: 35,  8: 25,            # Home&Kitchen → 60
    9: 30,  10: 25,           # Sports       → 55
    11: 45, 12: 40,           # Books        → 85
    13: 45, 14: 45,           # Beauty       → 90
}                              # TOTAL        = 500

# ============================================================================
# PRICING BY SUBCATEGORY
# ============================================================================
# (min_list_price, max_list_price, min_margin, max_margin)
# Margin = (list_price − unit_cost) / list_price
PRICING_CONFIG = {
    1:  (8_000,  80_000,  0.15, 0.30),   # Smartphones
    2:  (25_000, 1_50_000, 0.12, 0.25),  # Laptops
    3:  (500,    25_000,  0.25, 0.50),   # Headphones
    4:  (400,    4_000,   0.50, 0.70),   # Men's Wear
    5:  (500,    5_000,   0.50, 0.70),   # Women's Wear
    6:  (800,    12_000,  0.40, 0.60),   # Footwear
    7:  (300,    8_000,   0.35, 0.55),   # Cookware
    8:  (2_000,  40_000,  0.30, 0.50),   # Furniture
    9:  (500,    25_000,  0.30, 0.50),   # Fitness Equipment
    10: (300,    15_000,  0.30, 0.50),   # Camping Gear
    11: (150,    1_500,   0.45, 0.65),   # Fiction
    12: (200,    3_000,   0.40, 0.60),   # Non-Fiction
    13: (200,    5_000,   0.55, 0.75),   # Skincare
    14: (300,    4_000,   0.50, 0.70),   # Supplements
}

# ============================================================================
# BRANDS BY SUBCATEGORY
# ============================================================================
BRANDS = {
    1:  ["Samsung", "Apple", "OnePlus", "Xiaomi", "Vivo",
         "Oppo", "Realme", "Motorola", "Nothing", "Google"],
    2:  ["Dell", "HP", "Lenovo", "Asus", "Acer",
         "Apple", "MSI", "Microsoft"],
    3:  ["Sony", "JBL", "Bose", "Sennheiser", "boAt",
         "Noise", "Skullcandy", "Audio-Technica"],
    4:  ["Allen Solly", "Peter England", "Van Heusen", "Louis Philippe",
         "Levi's", "U.S. Polo", "Raymond", "Arrow"],
    5:  ["Zara", "H&M", "W", "Biba", "FabIndia",
         "Global Desi", "AND", "Aurelia"],
    6:  ["Nike", "Adidas", "Puma", "Reebok", "Bata",
         "Woodland", "Skechers", "Red Tape"],
    7:  ["Prestige", "Hawkins", "Pigeon", "Wonderchef",
         "Butterfly", "Milton", "Borosil"],
    8:  ["IKEA", "Nilkamal", "Godrej Interio", "Urban Ladder",
         "Wakefit", "Pepperfry", "HomeTown"],
    9:  ["Decathlon", "PowerMax", "Lifelong", "Cultsport",
         "Boldfit", "Cockatoo", "Fitkit"],
    10: ["Decathlon", "Wildcraft", "Quechua", "Coleman",
         "Trekmonk", "Naturehike", "Forclaz"],
    11: ["Penguin", "HarperCollins", "Rupa", "Hachette",
         "Pan Macmillan", "Bloomsbury", "Vintage"],
    12: ["Penguin", "Oxford", "Cambridge", "Wiley",
         "HarperCollins", "Simon & Schuster", "Rupa"],
    13: ["Lakme", "Mamaearth", "The Body Shop", "Nivea",
         "Cetaphil", "Himalaya", "Plum", "Dot & Key"],
    14: ["MuscleBlaze", "Optimum Nutrition", "HealthKart",
         "GNC", "Amway", "Oziva", "Wellbeing"],
}

# ============================================================================
# PRODUCT NAME TEMPLATES BY SUBCATEGORY
# ============================================================================
# Each list contains base product names. The generator combines these with
# brands and optional variant suffixes to produce 500 unique names.
PRODUCT_TEMPLATES = {
    1:  ["Galaxy S24", "Galaxy A55", "Galaxy M35", "iPhone 16", "iPhone 15",
         "iPhone SE", "Nord CE4", "Nord 4", "12 Pro", "Redmi Note 14",
         "Redmi 14C", "POCO X7", "V30", "V40", "T3 Pro", "Reno 12",
         "Find X8", "Narzo 70", "GT 6T", "C65", "Edge 50", "Razr 50",
         "Phone (2a)", "Phone (3)", "Pixel 9", "Pixel 8a"],
    2:  ["Inspiron 15", "XPS 13", "Latitude 14", "Pavilion 14", "Victus 16",
         "Spectre x360", "IdeaPad 3", "ThinkPad E16", "Legion 5",
         "Vivobook 15", "ROG Strix G16", "ZenBook 14", "Aspire 5",
         "Nitro V", "Swift Go 14", "MacBook Air M3", "MacBook Pro M3",
         "Katana 15", "Surface Laptop 6", "Surface Pro 10"],
    3:  ["WH-1000XM5", "WF-1000XM5", "Tune 770NC", "Live Pro 2",
         "QuietComfort Ultra", "700", "HD 450BT", "Momentum 4",
         "Rockerz 450", "Airdopes 141", "Buds Pro", "ColorBuds 2",
         "Hesh Evo", "Crusher ANC", "ATH-M50x", "ATH-M20x"],
    4:  ["Slim Fit Shirt", "Casual Polo", "Chino Trousers", "Denim Jacket",
         "Formal Blazer", "Linen Kurta", "Henley T-Shirt", "Oxford Shirt",
         "Jogger Pants", "Cargo Shorts", "V-Neck Sweater", "Track Pants",
         "Bomber Jacket", "Classic Jeans", "Mandarin Collar Shirt"],
    5:  ["Floral Kurti", "Palazzo Set", "Anarkali Dress", "Wrap Dress",
         "Embroidered Saree", "Crop Top", "Wide-Leg Pants", "Denim Jacket",
         "Maxi Dress", "Cotton Salwar", "A-Line Skirt", "Peplum Top",
         "Chanderi Dupatta", "Printed Leggings", "Shirt Dress"],
    6:  ["Air Max 90", "Ultraboost 23", "RS-X", "Classic Leather",
         "Power Perfect", "Woodland Trekker", "Go Walk 7", "Smith Derby",
         "Gel-Kayano 30", "Fresh Foam 1080", "Cortez", "Samba OG",
         "Suede Classic", "Nano X4", "Comfy Slip-On"],
    7:  ["Pressure Cooker 5L", "Non-Stick Tawa", "Kadhai Set", "Induction Cooktop",
         "Stainless Steel Pot", "Glass Casserole", "Mixer Grinder",
         "Electric Kettle", "Roti Maker", "Idli Maker", "Chopper",
         "Lunch Box Set", "Water Bottle 1L"],
    8:  ["Study Desk", "Office Chair", "Bookshelf 5-Tier", "TV Unit",
         "Shoe Rack", "Wardrobe 3-Door", "Bedside Table", "Sofa Set 3+1",
         "Dining Table 6-Seater", "Bean Bag XXL", "Wall Shelf Set",
         "Dressing Table"],
    9:  ["Treadmill T200", "Dumbbell Set 20kg", "Yoga Mat 6mm", "Resistance Bands",
         "Exercise Bike", "Pull-Up Bar", "Kettlebell 12kg", "Ab Roller",
         "Foam Roller", "Skipping Rope", "Weight Bench", "Spin Bike Pro"],
    10: ["Tent 4-Person", "Sleeping Bag 0°C", "Trekking Pole", "Headlamp 300L",
         "Hiking Backpack 50L", "Camp Stove", "Water Purifier", "Hammock",
         "Dry Bag 20L", "Compass Pro", "First Aid Kit", "Insulated Bottle"],
    11: ["The Midnight Library", "Atomic Habits Fiction", "The Alchemist",
         "Where the Crawdads Sing", "It Ends with Us", "Verity",
         "The Silent Patient", "Project Hail Mary", "Shantaram",
         "The God of Small Things", "A Suitable Boy", "Train to Pakistan",
         "The White Tiger", "Interpreter of Maladies", "Pachinko"],
    12: ["Atomic Habits", "Sapiens", "Thinking Fast and Slow", "Deep Work",
         "The Psychology of Money", "Ikigai", "Rich Dad Poor Dad",
         "Zero to One", "Start with Why", "The Lean Startup",
         "Educated", "Becoming", "Wings of Fire", "India After Gandhi"],
    13: ["Vitamin C Serum", "Sunscreen SPF 50", "Niacinamide Cream",
         "Aloe Vera Gel", "Face Wash 150ml", "Night Cream",
         "Sheet Mask Pack", "Lip Balm SPF 15", "Under Eye Cream",
         "Moisturizer 200ml", "Toner 100ml", "Face Scrub", "Body Lotion"],
    14: ["Whey Protein 1kg", "BCAA Powder", "Multivitamin 60ct",
         "Omega-3 Capsules", "Pre-Workout", "Creatine Monohydrate",
         "Vitamin D3 Drops", "Biotin Tablets", "Ashwagandha Extract",
         "Plant Protein 1kg", "Electrolyte Powder", "Collagen Peptides"],
}

# ============================================================================
# GEOGRAPHY — Indian cities with state/region mapping and population weight
# ============================================================================
# (city, state, region, weight)
# Weights are relative — they control customer share per city.
GEOGRAPHY = [
    # ── WEST (≈28% of customers) ──
    ("Mumbai",    "Maharashtra", "West", 6.0),
    ("Pune",      "Maharashtra", "West", 4.0),
    ("Ahmedabad", "Gujarat",     "West", 3.5),
    ("Surat",     "Gujarat",     "West", 2.5),
    ("Nagpur",    "Maharashtra", "West", 2.0),
    ("Nashik",    "Maharashtra", "West", 1.5),
    ("Vadodara",  "Gujarat",     "West", 1.5),
    ("Rajkot",    "Gujarat",     "West", 1.0),
    ("Panaji",    "Goa",         "West", 0.5),
    ("Jaipur",    "Rajasthan",   "West", 3.0),
    ("Jodhpur",   "Rajasthan",   "West", 1.5),
    ("Udaipur",   "Rajasthan",   "West", 1.0),

    # ── SOUTH (≈27% of customers) ──
    ("Bangalore",          "Karnataka",      "South", 6.0),
    ("Chennai",            "Tamil Nadu",     "South", 5.0),
    ("Hyderabad",          "Telangana",      "South", 5.0),
    ("Kochi",              "Kerala",         "South", 2.5),
    ("Coimbatore",         "Tamil Nadu",     "South", 2.0),
    ("Visakhapatnam",      "Andhra Pradesh", "South", 1.5),
    ("Mysore",             "Karnataka",      "South", 1.5),
    ("Thiruvananthapuram", "Kerala",         "South", 1.5),
    ("Madurai",            "Tamil Nadu",     "South", 1.0),
    ("Mangalore",          "Karnataka",      "South", 1.0),

    # ── NORTH (≈25% of customers) ──
    ("Delhi",      "Delhi",           "North", 6.0),
    ("Noida",      "Uttar Pradesh",   "North", 3.0),
    ("Gurgaon",    "Haryana",         "North", 3.0),
    ("Lucknow",    "Uttar Pradesh",   "North", 2.5),
    ("Chandigarh", "Punjab",          "North", 2.0),
    ("Amritsar",   "Punjab",          "North", 1.5),
    ("Dehradun",   "Uttarakhand",     "North", 1.0),
    ("Varanasi",   "Uttar Pradesh",   "North", 1.5),
    ("Kanpur",     "Uttar Pradesh",   "North", 1.5),
    ("Agra",       "Uttar Pradesh",   "North", 1.0),
    ("Patiala",    "Punjab",          "North", 0.5),
    ("Faridabad",  "Haryana",         "North", 1.5),

    # ── EAST (≈12% of customers) ──
    ("Kolkata",      "West Bengal", "East", 4.0),
    ("Bhubaneswar",  "Odisha",      "East", 2.0),
    ("Patna",        "Bihar",       "East", 2.0),
    ("Guwahati",     "Assam",       "East", 1.5),
    ("Ranchi",       "Jharkhand",   "East", 1.5),
    ("Siliguri",     "West Bengal", "East", 0.5),
    ("Jamshedpur",   "Jharkhand",   "East", 0.5),

    # ── CENTRAL (≈8% of customers) ──
    ("Bhopal",   "Madhya Pradesh", "Central", 2.5),
    ("Indore",   "Madhya Pradesh", "Central", 2.5),
    ("Raipur",   "Chhattisgarh",   "Central", 1.5),
    ("Jabalpur", "Madhya Pradesh", "Central", 1.0),
    ("Gwalior",  "Madhya Pradesh", "Central", 0.5),
]

# ============================================================================
# CUSTOMER DISTRIBUTIONS
# ============================================================================
GENDER_DIST = {"Male": 0.48, "Female": 0.48, "Other": 0.04}

AGE_GROUP_DIST = {
    "18-24": 0.20,
    "25-34": 0.35,
    "35-44": 0.25,
    "45-54": 0.13,
    "55+":   0.07,
}

SOURCE_DIST = {
    "Organic Search":  0.30,
    "Paid Ads":        0.25,
    "Social Media":    0.20,
    "Referral":        0.10,
    "Direct":          0.10,
    "Email Campaign":  0.05,
}

# ============================================================================
# CUSTOMER BEHAVIOR SEGMENTS
# ============================================================================
# (fraction_of_customers, min_orders, max_orders)
BEHAVIOR_DIST = {
    "one_time":   (0.65, 1, 1),
    "occasional": (0.20, 2, 5),
    "regular":    (0.10, 6, 10),
    "power":      (0.05, 11, 20),
}

# First-order timing: how soon after signup does the first order occur?
# (min_days, max_days) → probability
FIRST_ORDER_TIMING = [
    ((0, 7),     0.40),   # 40% order within first week
    ((8, 30),    0.25),   # 25% within first month
    ((31, 90),   0.20),   # 20% within first quarter
    ((91, 180),  0.15),   # 15% within first half-year
]

# ============================================================================
# ORDER ATTRIBUTE DISTRIBUTIONS
# ============================================================================
ORDER_STATUS_DIST = {
    "Completed":  0.82,
    "Processing": 0.05,
    "Cancelled":  0.08,
    "Returned":   0.05,
}

PAYMENT_METHOD_DIST = {
    "UPI":         0.35,
    "Credit Card": 0.20,
    "Debit Card":  0.18,
    "COD":         0.12,
    "Net Banking": 0.10,
    "Wallet":      0.05,
}

SHIPPING_COST_OPTIONS = [
    (0.00,   0.45),   # 45% free shipping
    (49.00,  0.30),   # 30% ₹49
    (99.00,  0.20),   # 20% ₹99
    (149.00, 0.05),   # 5%  ₹149
]

# ============================================================================
# SEASONALITY MULTIPLIERS
# ============================================================================
# Each entry: ((start_month, start_day), (end_month, end_day), multiplier)
# Used to bias order-date generation toward realistic peak/trough periods.
SEASONALITY = [
    ((10, 15), (11, 15), 1.8),   # Diwali festival season
    ((11, 20), (12,  5), 1.5),   # Black Friday / year-end sales
    ((1,   1), (1,  15), 1.3),   # New Year deals
    ((7,   1), (7,  31), 0.8),   # Monsoon lull
]

# ============================================================================
# ORDER-ITEMS DISTRIBUTIONS
# ============================================================================
ITEMS_PER_ORDER_DIST = {1: 0.25, 2: 0.30, 3: 0.22, 4: 0.13, 5: 0.10}

QUANTITY_DIST = {1: 0.70, 2: 0.20, 3: 0.07, 4: 0.02, 5: 0.01}

LINE_DISCOUNT_DIST = {
    0.0:  0.65,
    5.0:  0.15,
    10.0: 0.12,
    15.0: 0.05,
    20.0: 0.02,
    25.0: 0.01,
}

# Fraction of line items sold at exactly list_price (remainder get 5–20% off)
FULL_PRICE_FRACTION = 0.70

# Order-level discount tiers: (min_amount, max_amount) → probability
# Applied only to a fraction of orders. The rest have discount_amount = 0.
ORDER_DISCOUNT_TIERS = [
    (0.0,    0.0,    0.60),   # 60% no order-level discount
    (50.0,   200.0,  0.25),   # 25% small coupon
    (200.0,  500.0,  0.10),   # 10% medium coupon
    (500.0,  1500.0, 0.05),   # 5%  large coupon
]
