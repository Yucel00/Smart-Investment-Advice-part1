import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential
from keras.layers import LSTM, Dense, Dropout
from keras.callbacks import EarlyStopping
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, r2_score

# Verilerinizi yükleyin
doviz_df = pd.read_csv('doviz_kuru.csv')  # CSV dosyanızın adını burada girin

# Verileri zaman serisi modeline uygun hale getirmek için tarih sırasına göre düzenleyelim
doviz_df['Tarih'] = pd.to_datetime(doviz_df['Tarih'], format='%d-%m-%Y')  # %d-%m-%Y formatı gün-ay-yıl şeklindedir
doviz_df = doviz_df.sort_values(by='Tarih')

# NaN değerlerini GBP sütununda ortalama ile dolduralım
doviz_df.replace([np.inf, -np.inf], np.nan, inplace=True)  # Sonsuz değerleri NaN ile değiştir
doviz_df.dropna(inplace=True)  # Tüm NaN değerleri kaldır

# Sadece GBP fiyatlarını alalım
doviz_values_gbp = doviz_df['GBP'].values.reshape(-1, 1)

# Verileri Min-Max ölçekleme ile normalleştirelim (LSTM için gerekli)
scaler_gbp = MinMaxScaler(feature_range=(0, 1))
scaled_gbp = scaler_gbp.fit_transform(doviz_values_gbp)

# Zaman serisi veri yapısı için bir yardımcı fonksiyon
def create_dataset(dataset, time_step=1):
    X, Y = [], []
    for i in range(len(dataset) - time_step - 1):
        a = dataset[i:(i + time_step), 0]  # X olarak
        X.append(a)
        Y.append(dataset[i + time_step, 0])  # Y olarak
    return np.array(X), np.array(Y)

# 60 adım (2 ay) geriye giderek veri setimizi hazırlayalım
time_step = 60

# GBP için veri seti oluşturma
X_gbp, Y_gbp = create_dataset(scaled_gbp, time_step)
X_gbp = X_gbp.reshape(X_gbp.shape[0], X_gbp.shape[1], 1)

# Eğitim ve test setlerini %80 - %20 oranında bölelim
def split_data(X, Y):
    train_size = int(len(X) * 0.8)
    X_train, X_test = X[0:train_size], X[train_size:len(X)]
    Y_train, Y_test = Y[0:train_size], Y[train_size:len(Y)]
    return X_train, X_test, Y_train, Y_test

# GBP verilerini böl
X_train_gbp, X_test_gbp, Y_train_gbp, Y_test_gbp = split_data(X_gbp, Y_gbp)

# Modeli oluşturma fonksiyonu
def create_lstm_model():
    model = Sequential()
    model.add(LSTM(units=50, return_sequences=True, input_shape=(time_step, 1)))
    model.add(Dropout(0.2))
    model.add(LSTM(units=50, return_sequences=False))
    model.add(Dropout(0.2))
    model.add(Dense(25))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mean_squared_error')
    return model

# Modeli oluştur ve eğit
def train_model(X_train, Y_train, X_test, Y_test, scaler):
    model = create_lstm_model()
    early_stop = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
    model.fit(X_train, Y_train, batch_size=32, epochs=100, verbose=1, 
              validation_data=(X_test, Y_test), callbacks=[early_stop])
    
    # Tahmin yap
    train_predict = model.predict(X_train)
    test_predict = model.predict(X_test)
    
    # Verileri orijinal ölçeklerine geri çevirelim
    train_predict = scaler.inverse_transform(train_predict)
    test_predict = scaler.inverse_transform(test_predict)
    Y_test_inv = scaler.inverse_transform(Y_test.reshape(-1, 1))  # Y_test'i de orijinal haline getiriyoruz
    
    return train_predict, test_predict, Y_test_inv

# GBP modeli eğit ve tahmin yap
train_predict_gbp, test_predict_gbp, Y_test_gbp_inv = train_model(X_train_gbp, Y_train_gbp, X_test_gbp, Y_test_gbp, scaler_gbp)

# Sonuçları görselleştirme
def plot_results(currency_name, real_data, train_predict, test_predict, time_step):
    plt.figure(figsize=(10, 6))

    # Boyutları düzeltme (flatten ile 2D'den 1D'ye indirgeme)
    train_predict = train_predict.flatten()
    test_predict = test_predict.flatten()
    
    # Eğitim tahminlerini çizelim (60 adım geriye gittiğimiz için başlangıcı kaydırıyoruz)
    plt.plot(doviz_df['Tarih'], real_data, label=f'Gerçek {currency_name} Fiyatları', color='blue')
    plt.plot(doviz_df['Tarih'][time_step:len(train_predict) + time_step], train_predict, label=f'Eğitim Tahminleri', color='green')
    
    # Test tahminlerini çizelim (eğitim tahminlerinin bittiği noktadan başlamalı)
    test_start_idx = len(train_predict) + (time_step)  # Test tahminlerinin başladığı yer
    test_end_idx = test_start_idx + len(test_predict)  # Test tahminlerinin bittiği yer
    plt.plot(doviz_df['Tarih'][test_start_idx:test_end_idx], test_predict, label=f'Test Tahminleri', color='red')

    # Grafik ayarları
    plt.xlabel('Tarih')
    plt.ylabel(f'{currency_name} Fiyatı')
    plt.title(f'{currency_name} Fiyatı LSTM Model Tahminleri')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


# GBP tahminlerini görselleştirme
plot_results('GBP', doviz_df['GBP'], train_predict_gbp, test_predict_gbp, time_step)

# MSE ve R2 Score hesaplama fonksiyonu
def calculate_metrics(y_true, y_pred):
    mse = mean_squared_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    return mse, r2

# GBP için MSE ve R2 Score
mse_gbp, r2_gbp = calculate_metrics(Y_test_gbp_inv, test_predict_gbp)

# Sonuçları ekrana yazdıralım
print(f"GBP için MSE: {mse_gbp}")
print(f"GBP için R² Score: {r2_gbp}")