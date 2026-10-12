import sys
import numpy as np
from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, WindowOperations

class EEGVisualizer(QtWidgets.QMainWindow):
    def __init__(self, board, board_id):
        super().__init__()
        self.board = board
        self.board_id = board_id
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        
        self.setWindowTitle("BrainFlow - Muse S Athena (Normalisé & Télémétrie)")
        self.resize(1100, 650)
        
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Barre d'état utile en haut
        self.status_label = QtWidgets.QLabel("Analyse en cours... Clignez des yeux pour tester.")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #3498db; padding: 5px;")
        main_layout.addWidget(self.status_label)
        
        # Graphiques
        graph_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(graph_layout)
        
        self.win_raw = pg.GraphicsLayoutWidget()
        graph_layout.addWidget(self.win_raw, stretch=3)
        
        self.win_waves = pg.GraphicsLayoutWidget()
        graph_layout.addWidget(self.win_waves, stretch=1)
        
        self.init_plots()
        
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(50)

    def init_plots(self):
        self.curves = []
        # Correction de la nomenclature selon le système international 10-20
        channel_names = ["TP9 (Oreille G)", "AF7 (Front G)", "AF8 (Front D)", "TP10 (Oreille D)"]
        
        for i, name in enumerate(channel_names):
            p = self.win_raw.addPlot(row=i, col=0)
            p.setLabel('left', name, units='uV')
            p.setYRange(-150, 150) # Fixe l'échelle pour éviter les sauts brusques
            p.showGrid(x=True, y=True)
            if i < 3:
                p.getAxis('bottom').setStyle(showValues=False)
            else:
                p.setLabel('bottom', 'Échantillons temporels')
            
            curve = p.plot(pen=pg.mkPen(color=pg.intColor(i), width=1.5))
            self.curves.append(curve)
            
        self.plot_waves = self.win_waves.addPlot()
        self.plot_waves.setLabel('left', "Proportion de l'onde", units='%')
        self.plot_waves.setYRange(0, 100) # Échelle fixe de 0 à 100%
        self.plot_waves.setXRange(-0.5, 3.5)
        self.plot_waves.getAxis('bottom').setTicks([[ (0, 'Delta'), (1, 'Theta'), (2, 'Alpha'), (3, 'Beta') ]])
        
        self.bar_graph = pg.BarGraphItem(x=[0, 1, 2, 3], height=[0, 0, 0, 0], width=0.6, brush='#2ecc71')
        self.plot_waves.addItem(self.bar_graph)

    def update_data(self):
        # Utiliser l'index du preset p1035 (l'EEG est sur le preset principal par défaut)
        data = self.board.get_current_board_data(1000)
        if data.shape[1] < 256:  
            return

        delta_total, theta_total, alpha_total, beta_total = 0, 0, 0, 0
        blink_detected = False

        for i, channel in enumerate(self.eeg_channels):
            # Faire une copie locale pour éviter de modifier le tampon en place de manière agressive
            channel_data = np.copy(data[channel])
            
            # Détection de clignement (pics > 120 uV sur les capteurs frontaux AF7/AF8, index 1 et 2)
            if i in [1, 2] and np.max(np.abs(channel_data[-50:])) > 120:
                blink_detected = True
            
            # Filtrage Numérique DSP (Le filtre passe-haut à 1.0Hz remplace le detrend linéaire instable)
            DataFilter.perform_bandstop(channel_data, self.sampling_rate, 48.0, 52.0, 2, FilterTypes.BUTTERWORTH.value, 0)
            DataFilter.perform_bandpass(channel_data, self.sampling_rate, 1.0, 45.0, 2, FilterTypes.BUTTERWORTH.value, 0)
            
            self.curves[i].setData(channel_data)
            
            # Transformée de Fourier Rapide (FFT / Méthode Welch)
            nfft = DataFilter.get_nearest_power_of_two(self.sampling_rate)
            psd = DataFilter.get_psd_welch(channel_data, nfft, nfft // 2, self.sampling_rate, WindowOperations.HANNING.value)
            
            # Accumulation de la puissance spectrale par bande
            delta_total += DataFilter.get_band_power(psd, 1.0, 4.0)
            theta_total += DataFilter.get_band_power(psd, 4.0, 8.0)
            alpha_total += DataFilter.get_band_power(psd, 8.0, 13.0)
            beta_total += DataFilter.get_band_power(psd, 13.0, 30.0)

        # Mise à jour de la barre d'état
        if blink_detected:
            self.status_label.setText("⚠️ CLIGNEMENT D'ŒIL DÉTECTÉ (Activité musculaire frontale)")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")
        else:
            self.status_label.setText("🧠 Signal EEG stable - Analyse en continu...")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2ecc71;")

        # Calcul des proportions relatives (%)
        grand_total = delta_total + theta_total + alpha_total + beta_total
        if grand_total > 0:
            pct_delta = (delta_total / grand_total) * 100
            pct_theta = (theta_total / grand_total) * 100
            pct_alpha = (alpha_total / grand_total) * 100
            pct_beta = (beta_total / grand_total) * 100
            
            self.bar_graph.setOpts(height=[pct_delta, pct_theta, pct_alpha, pct_beta])

def main():
    BoardShim.set_log_level(3)
    params = BrainFlowInputParams()
    params.mac_address = "..." # Mettre votre adresse MAC ici
    params.other_info = "preset=p1035;low_latency=true"
    params.timeout = 15

    board_id = BoardIds.MUSE_S_ATHENA_BOARD.value
    board = BoardShim(board_id, params)

    try:
        board.prepare_session()
        board.start_stream()
        
        app = QtWidgets.QApplication(sys.argv)
        visualizer = EEGVisualizer(board, board_id)
        visualizer.show()
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Erreur d'exécution : {e}")
    finally:
        if board.is_prepared():
            board.stop_stream()
            board.release_session()
            print("Session Bluetooth fermée proprement.")

if __name__ == "__main__":
    main()
