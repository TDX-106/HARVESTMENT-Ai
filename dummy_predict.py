import json
from predictor import YieldPredictor

def main():
    print("Loading the updated 97.4% accurate models...\n")
    model = YieldPredictor(model_dir="saved_models")

    # Creating some dummy data for a farmer in Gujarat
    dummy_data_1 = {
        "district": "Rajkot", 
        "crop": "Cotton(lint)", 
        "season": "Kharif",
        "area": 10.0, # 10 hectares
        "min_temp": 24.0, 
        "max_temp": 33.5,
        "total_rain": 600.0, 
        "humidity_avg": 70.0,
        "yearly_min_temp": 22.0, 
        "yearly_max_temp": 34.0,
        "yearly_total_rain": 750.0, 
        "yearly_humidity_avg": 60.0,
        "soil_type": "Black", 
        "soil_fertility_score": 6.5, 
        "irrigation_score": 0.8
    }

    dummy_data_2 = {
        "district": "Banaskantha", 
        "crop": "Potato", 
        "season": "Rabi",
        "area": 5.0, # 5 hectares
        "min_temp": 12.0, 
        "max_temp": 28.0,
        "total_rain": 10.0, 
        "humidity_avg": 40.0,
        "yearly_min_temp": 18.0, 
        "yearly_max_temp": 35.0,
        "yearly_total_rain": 400.0, 
        "yearly_humidity_avg": 45.0,
        "soil_type": "Alluvial", 
        "soil_fertility_score": 8.0, 
        "irrigation_score": 1.0 # Fully irrigated
    }

    print("=== DUMMY TEST 1: Cotton in Rajkot (Kharif) ===")
    result_1 = model.predict(**dummy_data_1)
    print(f"Predicted Yield  : {result_1['predicted_yield']} tonnes per hectare")
    print(f"Worst-case Yield : {result_1['min_yield']} tonnes per hectare (Pessimistic)")
    print(f"Best-case Yield  : {result_1['max_yield']} tonnes per hectare (Optimistic)")
    print(f"Total Production : {result_1['total_predicted']} tonnes for 10 hectares\n")

    print("=== DUMMY TEST 2: Potato in Banaskantha (Rabi) ===")
    result_2 = model.predict(**dummy_data_2)
    print(f"Predicted Yield  : {result_2['predicted_yield']} tonnes per hectare")
    print(f"Worst-case Yield : {result_2['min_yield']} tonnes per hectare (Pessimistic)")
    print(f"Best-case Yield  : {result_2['max_yield']} tonnes per hectare (Optimistic)")
    print(f"Total Production : {result_2['total_predicted']} tonnes for 5 hectares\n")

if __name__ == "__main__":
    main()
