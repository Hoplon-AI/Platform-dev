import csv


def load_postcode_data():
    postcode_data = {}
    with open("postcodez.csv", mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)

        for row in reader:
            postcode_data[row[0].strip().upper()] = row[4]
    return postcode_data


pc_data = load_postcode_data()


def postcode_deprivation_index(pc):
    pc = pc.strip().upper()
    return pc_data[pc]


postcode = input("Enter your postcode: ").strip().upper()

if postcode in pc_data:
    print(f"The deprivation index for postcode {postcode} is: {pc_data[postcode]}")
else:
    print(f"Postcode {postcode} not found in the dataset.")