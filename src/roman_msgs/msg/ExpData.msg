# Message published by generator.py on /exp_data
# Contains experiment item data for the interface

string item_name
string difficulty
string ground_truth
string classification   # "justification" or "no_justification"
bool suggestion # false or true
int32 box_index         # 0-7 (0-3 justification, 4-7 no_justification)
