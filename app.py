from data_pipeline.ingestion.nse_client import NSE_Client
from utils.constants import Index

if __name__ == "__main__":
    nse_client = NSE_Client()
    print(nse_client.get_data("NIFTY 50"))