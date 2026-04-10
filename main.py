import tensil

# Read a .tsl file
sheet = tensil.read("fault_codes.tsl")

# Look at the data
print(sheet.name)                  # "fault_codes"
print(sheet.rows[0])               # {"code": 1001, "severity": "WARNING", ...}
print(sheet["threshold", 1002])    # 85

# Validate it
errors = tensil.validate("fault_codes.tsl")
for e in errors:
    print(e)

# Evaluate formulas
tensil.evaluate(sheet)
