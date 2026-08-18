import sys
from test_full_pipeline import run_test

def main():
    print("=======================================================")
    print(" RUNNING HACKATHON EXPECTED OUTPUT SAMPLES")
    print("=======================================================")
    
    samples = [
        {
            "brand": "Frigidaire",
            "mpn": "PDSH4816AF",
            "description": "PDSH4816AF Dishwasher SS - Display Only"
        },
        {
            "brand": "Whirlpool",
            "mpn": "WDTS7024RZ",
            "description": "WDTS7024RZ Dishwasher SS - Display Only"
        }
    ]
    
    # Check for interactive mode flag
    interactive = "--no-hitl" not in sys.argv

    for item in samples:
        print(f"\n>>> TESTING: {item['brand']} {item['mpn']} <<<\n")
        try:
            run_test(
                brand=item['brand'],
                mpn=item['mpn'],
                description=item['description'],
                interactive_hitl=interactive
            )
        except Exception as e:
            print(f"FAILED on {item['mpn']}: {e}")

if __name__ == "__main__":
    main()
