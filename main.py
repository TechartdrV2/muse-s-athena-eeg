import time
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

def main():
    # Activer les logs de BrainFlow pour le debug en console
    BoardShim.enable_dev_board_logger()
    #BoardShim.set_log_level(3)

    # Configuration des paramètres d'entrée
    params = BrainFlowInputParams()
    
    # !!! REMPLACEZ PAR VOTRE ADRESSE MAC TROUVÉE À L'ÉTAPE 2 !!!
    params.mac_address = "..." 
    
    # Spécification du protocole natif pour le Muse S Athena (EEG + fNIRS)
    params.other_info = "preset=p1035;low_latency=true"
    
    # Force BrainFlow à chercher le bandeau pendant 15 secondes au lieu de 6
    params.timeout = 15 

    # Récupération de l'identifiant de la carte Muse S Athena
    board_id = BoardIds.MUSE_S_ATHENA_BOARD.value
    board = BoardShim(board_id, params)

    try:
        print("Connexion au Muse S Athena en cours...")
        board.prepare_session()
        
        print("Démarrage du flux de données...")
        board.start_stream() 
        
        # Acquisition des données pendant 5 secondes
        time.sleep(5)

        # Extraction de la matrice de données accumulées (canaux x échantillons)
        data = board.get_board_data() 
        
        # Récupération exclusive des index des canaux EEG
        eeg_channels = BoardShim.get_eeg_channels(board_id)
        
        print(f"\n[SUCCÈS] Échantillons récupérés : {data.shape[1]}")
        print("Données EEG brutes des premiers échantillons (lignes = canaux, colonnes = temps) :")
        print(data[eeg_channels])

    except Exception as e:
        print(f"\n[ERREUR] Une erreur est survenue : {e}")
        
    finally:
        # Libération systématique de la session et du contrôleur Bluetooth
        if board.is_prepared():
            print("Arrêt du flux et fermeture propre de la session.")
            board.stop_stream()
            board.release_session()

if __name__ == "__main__":
    main()