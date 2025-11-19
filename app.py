#@title 2. 啟動 Flask 混音伺服器 (置中 + 手動延遲版)
from flask import Flask, request, send_file
import json
import os
from pydub import AudioSegment


app = Flask(__name__)


def speed_change(sound, speed=1.0):
    sound_with_altered_frame_rate = sound._spawn(sound.raw_data, overrides={
        "frame_rate": int(sound.frame_rate * speed)
    })
    return sound_with_altered_frame_rate.set_frame_rate(sound.frame_rate)

@app.route('/mix', methods=['POST'])
def mix_audio():
    try:
        print("📥 收到混音請求...")
        
        if 'original_audio' not in request.files: return "Missing original", 400
        original_file = request.files['original_audio']
        original_path = "/content/original_input.webm"
        original_file.save(original_path)
        
        base_audio = AudioSegment.from_file(original_path)
        final_audio = base_audio

        if 'censor_rules' not in request.form: return "Missing rules", 400
        try:
            censor_rules = json.loads(request.form['censor_rules'])
            if not isinstance(censor_rules, list): censor_rules = [censor_rules]
        except: return "Invalid JSON", 400

        for i, rule in enumerate(censor_rules):
            file_key = f"replacement_{i}"
            if file_key not in request.files: continue
            
            rep_file = request.files[file_key]
            rep_file.seek(0, os.SEEK_END)
            if rep_file.tell() < 100: continue
            rep_file.seek(0)

            rep_path = f"/content/temp_rep_{i}.wav"
            rep_file.save(rep_path)
            
            try:
                replace_audio = AudioSegment.from_file(rep_path)

                # ==============================
                # 🎛️ 手動調整區 (Manual Adjustment)
                # ==============================
                
                # ★ 在這裡設定您要延遲多久 (毫秒)
                # 正數 = 延後 (例如 200)
                # 負數 = 提早 (例如 -100)
                MANUAL_DELAY_MS = 100  
                
                # 解析原始時間
                start_s = float(str(rule['start_time']).replace('s', ''))
                end_s = float(str(rule['end_time']).replace('s', ''))
                
                original_start_ms = int(start_s * 1000)
                original_end_ms = int(end_s * 1000)
                original_duration_ms = original_end_ms - original_start_ms

                # 變速處理
                current_len = len(replace_audio)
                if original_duration_ms > 0:
                    calculated_speed = current_len / original_duration_ms
                else:
                    calculated_speed = 1.0
                
                speed_factor = max(0.8, min(calculated_speed, 1.2))
                adjusted_audio = speed_change(replace_audio, speed=speed_factor)

                # 音量增強
                adjusted_audio = adjusted_audio + 20

                # --- 計算最終位置 ---
                
                # 1. 先算置中位移
                replacement_duration_ms = len(adjusted_audio)
                center_offset = (original_start_ms + original_end_ms) / 2
                
                # 2. 加上原本的開始時間 + 置中位移 + 手動延遲
                final_position_ms = int(center_offset + MANUAL_DELAY_MS)
                
                # 防呆：不可以小於 0
                final_position_ms = max(0, final_position_ms)

                print(f"   Processing: '{rule.get('replacement')}' at {final_position_ms}ms (Delay: {MANUAL_DELAY_MS}ms)")
                
                final_audio = final_audio.overlay(adjusted_audio, position=final_position_ms)

            except Exception as e:
                print(f"❌ Error: {e}")
                continue

        output_path = "/content/final_censored.mp3"
        final_audio.export(output_path, format="mp3")
        return send_file(output_path, mimetype="audio/mpeg", as_attachment=True, download_name="final.mp3")

    except Exception as e:
        print(f"❌ Server Error: {e}")
        return str(e), 500

if __name__ == '__main__':
    # 關鍵：讓它監聽所有網路介面，端口使用 Render 的環境變數
    port = int(os.environ.get('PORT', 5000)) 
    app.run(host='0.0.0.0', port=port)
