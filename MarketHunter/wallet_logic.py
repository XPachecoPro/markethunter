import requests
import time

class SmartMoneyWatcher:
    def __init__(self, watch_list=None, etherscan_api_key="YOUR_API_KEY"):
        self.watch_list = watch_list or []
        self.api_key = etherscan_api_key
        # Dicionário para guardar os tokens que a carteira já possui
        self.wallet_history = {address: set() for address in self.watch_list}

    def check_smart_money_movements(self):
        alerts = []
        for address in self.watch_list:
            # print(f"Monitorando carteira: {address}") # Debug
            txs = self.get_latest_token_transactions(address)
            
            for tx in txs:
                token_symbol = tx.get('tokenSymbol')
                token_address = tx.get('contractAddress')
                
                # Se for uma transação de entrada (compra/recebimento)
                if tx.get('to').lower() == address.lower():
                    if token_address not in self.wallet_history[address]:
                        # Primeiro registro ou token novo detectado
                        # Para o primeiro scan, apenas populamos o histórico
                        if len(self.wallet_history[address]) > 0:
                            alerts.append({
                                'wallet': address,
                                'token': token_symbol,
                                'contract': token_address
                            })
                        self.wallet_history[address].add(token_address)
        return alerts

    def get_latest_token_transactions(self, address):
        """
        Busca as últimas transações de tokens ERC-20 via Etherscan API.
        """
        if self.api_key == "YOUR_API_KEY":
            # Mock para demonstração se não houver chave
            return []
            
        url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={address}&page=1&offset=10&sort=desc&apikey={self.api_key}"
        
        try:
            response = requests.get(url)
            data = response.json()
            if data.get('status') == '1':
                return data.get('result', [])
            return []
        except Exception as e:
            print(f"Erro ao buscar transações: {e}")
            return []

if __name__ == "__main__":
    # Exemplo de uso
    watcher = SmartMoneyWatcher(watch_list=["0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"]) # Vitalik (Exemplo)
    print("Iniciando monitoramento de Smart Money...")
    # No primeiro run, ele apenas mapeia o que já tem. 
    # Em runs subsequentes, ele alerta para tokens novos.
    watcher.check_smart_money_movements()
    print("Mapeamento inicial concluído. Aguardando novas movimentações...")
