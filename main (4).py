import tkinter as tk
from PIL import Image, ImageTk
from tkinter import messagebox, scrolledtext, simpledialog, ttk, Toplevel, Listbox, Toplevel, Scrollbar
import serial
import serial.tools.list_ports
import pygame
from stable_baselines3 import PPO  # Thư viện RL
from environment import SpeechCorrectionEnv  # Môi trường RL bạn cần tạo
import os
import time
import threading
import io
from gtts import gTTS
from pydub import AudioSegment
import speech_recognition as sr
import random
import re
import tempfile
from collections import defaultdict
import chardet


def detect_file_encoding(file_path):
    with open(file_path, "rb") as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def read_file_with_detected_encoding(file_path):
    encoding = detect_file_encoding(file_path)
    print(f"Mã hóa phát hiện: {encoding}")
    with open(file_path, "r", encoding=encoding, errors='ignore') as file:
        return file.readlines()


# Initialize pygame for audio
pygame.mixer.init()

audioWavTam = 'C:\\Users\\LENOVO\\Downloads\\App (1)\\App\\audioWavTam.wav'
# Lấy đường dẫn đến thư mục hiện tại
current_directory = os.getcwd()
# Đường dẫn đến file âm thanh tạm thời
audioWavTam = os.path.join(current_directory, 'audioWavTam.wav')

# Constants for eye and mouth animations
EYE_RADIUS = 50
PUPIL_RADIUS = 25
EYELID_HEIGHT = 10  # Height of the eyelids
CHOP_MAT = 10000
SLIDE_VALUES = {
    1: (1, 9, 1), 2: (1, 9, 1), 3: (-9, 5, 1), 4: (-9, 3, 1), 5: (-9, 3, 1), 6: (-9, 5, 1), 7: (0, 9, 1), 8: (1, 9, 1),
    9: (1, 9, 1), 10: (1, 9, 1), 11: (1, 9, 1), 12: (1, 9, 1), 13: (1, 9, 1), 14: (1, 9, 1), 15: (1, 9, 1),
    16: (0, 9, 1)
}

CHAT_TEMP_FILE = "Default.HOC"  # File lưu đoạn hội thoại
STUTTER_FILE = "Default.DEF"  # File lưu các từ đặc biệt
KICHBAN_FILE = "Default.KB"
positive_feedback = ["đúng rồi", "khá tốt", "tốt", "bạn đã làm rất tốt", "tuyệt vời"]


class SpeechFrame(tk.Frame):
    def __init__(self, setup_app, master):
        super().__init__(master)
        self.setup_app = setup_app

        # Đọc và áp dụng các thiết lập từ file fix_stuttering.BOT
        self.load_stuttering_settings()

        # Tạo khung và các phần tử giao diện (các phần khác không thay đổi)

        self.current_eye_state = "Eye1"  # Mặc định là Eye1
        self.random_eye_timer = None  # Timer để quản lý chuyển đổi mắt
        self.consecutive_correct = 0
        self.total_sentences = 0
        self.correct_sentences = 0
        self.wrong_sentences = {}
        self.corrected_sentences = defaultdict(int)  # Đếm số lần câu Corrected xuất hiện

        # File .HOC hiện hành
        self.current_hoc_file = CHAT_TEMP_FILE

        if not os.path.exists(self.current_hoc_file):
            open(self.current_hoc_file, "w").close()

        # Khởi tạo frame cho chatbox với tiêu đề chứa tên file .HOC hiện hành

        self.chatbox_frame = tk.LabelFrame(master, text=f"Tập luyện - ({self.current_hoc_file})",
                                           font=("Arial", 16, "bold"), labelanchor='n')
        self.chatbox_frame.grid(row=0, column=2, padx=10, pady=10)

        # Khung hội thoại (chat log)
        self.chat_log = scrolledtext.ScrolledText(self.chatbox_frame, width=35, height=13, wrap=tk.WORD)
        self.chat_log.grid(row=1, column=0, columnspan=4)
        self.chat_log.bind("<<Modified>>", self.on_chat_log_modified)
        # Nút bắt đầu nhận diện giọng nói với hình ảnh "mic"
        self.speak_button = tk.Button(
            self.chatbox_frame,
            text="Mic",
            command=self.recognize_speech,
            image=self.setup_app.image_manager.get_image("mic"),  # Thay "mic" bằng tên key ảnh phù hợp
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        self.speak_button.grid(row=0, column=1)

        # Nút phân tích chat với hình ảnh "analyze"
        self.analyze_button = tk.Button(
            self.chatbox_frame,
            text="Analyze",
            command=self.analyze_chat,
            image=self.setup_app.image_manager.get_image("analyze"),  # Thay "analyze" bằng tên key ảnh phù hợp
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        self.analyze_button.grid(row=0, column=2)

        # Nút mở cài đặt với hình ảnh "option"
        self.option_button = tk.Button(
            self.chatbox_frame,
            text="Options",
            command=self.show_options,
            image=self.setup_app.image_manager.get_image("option"),  # Thay "option" bằng tên key ảnh phù hợp
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        self.option_button.grid(row=0, column=3)

        # Nhãn hiển thị phản hồi không cần thay đổi vì nó không phải là nút
        self.response_label = tk.Label(self.chatbox_frame, text="", wraplength=300, justify="left", anchor="w")
        self.response_label.grid(row=3, column=0, columnspan=4, sticky="w")

        # Nút mở quản lý file .HOC (người học) với hình ảnh "use"
        self.hoc_button = tk.Button(
            self.chatbox_frame,
            text="Use",
            command=self.manage_hoc_files,
            image=self.setup_app.image_manager.get_image("use"),  # Thay "use" bằng tên key ảnh phù hợp
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        self.hoc_button.grid(row=0, column=0)

        # Nhãn cho Listbox "Những câu cần chỉnh sửa"
        self.corrected_label = tk.Label(self.chatbox_frame, text="Những câu cần chỉnh sửa", font=("Arial", 14, "bold"))
        self.corrected_label.grid(row=2, column=0,columnspan=4)

        # Listbox để hiển thị các câu "Corrected"
        self.corrected_listbox = tk.Listbox(self.chatbox_frame, height=12, width=30)
        self.corrected_listbox.grid(row=3, column=0, columnspan=4)

        # Load các thiết lập về việc lắp bắp
        self.load_stuttering_settings()

        # Nạp nội dung file .HOC và cập nhật Listbox
        self.load_chat_log_from_file()
        self.update_corrected_listbox()

        # Thêm sự kiện double-click vào listbox
        self.corrected_listbox.bind("<Double-Button-1>", self.on_listbox_double_click)

        # Áp dụng trạng thái tự động thay đổi mắt từ file
        if self.auto_eye:
            self.toggle_eye_mode()  # Kích hoạt chế độ tự động thay đổi mắt nếu auto_eye = True

        # TextBox để nhập giá trị mới
        self.new_item_entry = tk.Entry(self.chatbox_frame, width=30)
        self.new_item_entry.grid(row=4, column=1, columnspan=3)

        # Nút "+" để thêm giá trị mới vào Listbox
        self.add_button = tk.Button(self.chatbox_frame, text="+", command=self.add_to_listbox_and_file)
        self.add_button.grid(row=4, column=0, pady=5)

    def add_to_listbox_and_file(self):
        """Thêm mục từ textbox vào file .HOC dưới dạng 'Corrected:' và cập nhật lại listbox và chatbox."""
        # Lấy giá trị từ TextBox và chuyển về chữ thường
        new_item = self.new_item_entry.get().strip().lower()

        # Kiểm tra nếu textbox không trống và không có trong listbox (so sánh không tính phần trong dấu ngoặc vuông)
        if new_item and new_item not in [self.remove_square_brackets(item).lower() for item in
                                         self.corrected_listbox.get(0, tk.END)]:
            # Thêm dòng "Corrected: <nội dung textbox>" vào cuối file .HOC
            try:
                with open(self.current_hoc_file, "a") as hoc_file:
                    hoc_file.write(f"Corrected: {new_item}\n")  # Ghi dòng mới vào file
            except FileNotFoundError:
                messagebox.showerror("Error", f"Cannot open file {self.current_hoc_file}")

            # Cập nhật lại listbox sau khi thêm dòng mới vào file
            self.update_corrected_listbox()

            # Cập nhật chatbox với câu mới thêm
            self.chat_log.insert(tk.END, f"Corrected: {new_item}\n")
            self.chat_log.see(tk.END)  # Đảm bảo chatbox cuộn đến dòng cuối cùng

            # Xóa nội dung trong textbox
            self.new_item_entry.delete(0, tk.END)
        else:
            # Nếu textbox trống hoặc giá trị đã tồn tại trong listbox
            messagebox.showwarning("Warning", "The item already exists or is empty.")

    def remove_square_brackets(self, item):
        """Loại bỏ phần trong dấu ngoặc vuông (nếu có)."""
        if "[" in item:
            item = item.split("[")[0].strip()
        return item

    def show_options(self):
        """Hiển thị cửa sổ tùy chọn để thêm/xóa các từ lắp bắp"""
        option_window = tk.Toplevel(self)
        option_window.title("Options")
        option_window.geometry("250x280")  # Ví dụ: rộng 400, cao 300
        # Đặt cửa sổ Option luôn nổi trước cửa sổ chính
        option_window.transient(self.master)
        option_window.grab_set()
        option_window.focus_set()

        # Checkbox cho từ đặc biệt
        self.special_word_var = tk.IntVar(value=int(self.special_word_check))
        special_word_check = tk.Checkbutton(option_window, text="Những từ đặc biệt", variable=self.special_word_var)
        special_word_check.grid(row=0, column=0, columnspan=4, padx=5, pady=5)

        # Listbox cho các cụm từ
        self.phrase_listbox = tk.Listbox(option_window, height=6)
        self.phrase_listbox.grid(row=2, column=0, columnspan=3, rowspan=2, padx=5, pady=5)
        for phrase in self.allowed_phrases:
            self.phrase_listbox.insert(tk.END, phrase)

        add_button = tk.Button(option_window, text="+", command=self.add_phrase)
        add_button.grid(row=2, column=5)

        delete_button = tk.Button(option_window, text="-", command=self.delete_phrase)
        delete_button.grid(row=3, column=5, sticky="e")

        save_button = tk.Button(option_window, text="Save & Exit",
                                command=lambda: self.save_and_close_options(option_window))
        save_button.grid(row=5, column=0)

        # Thêm checkbox cho Eye mode
        self.auto_eye_var = tk.IntVar(value=int(self.auto_eye))  # Biến trạng thái cho checkbox
        eye_mode_check = tk.Checkbutton(option_window, text="Tự động thay đổi mắt", variable=self.auto_eye_var)
        eye_mode_check.grid(row=1, column=0, columnspan=4)

        # Thêm thanh trượt thời gian ghi âm
        self.recording_time_var = tk.IntVar(value=self.recording_time_limit)  # Biến cho thời gian ghi âm
        recording_time_slider = tk.Scale(option_window, from_=5, to=120, orient=tk.HORIZONTAL,
                                         label="Thời gian ghi âm (giây)", variable=self.recording_time_var, length=180)
        recording_time_slider.grid(row=4, column=0, columnspan=4, padx=5, pady=5, sticky="w")  # căn lề trái

    def save_and_close_options(self, window):
        """Lưu cài đặt từ lắp bắp và trạng thái tự động thay đổi mắt và đóng cửa sổ tùy chọn"""
        self.special_word_check = bool(self.special_word_var.get())
        self.allowed_phrases = list(self.phrase_listbox.get(0, tk.END))

        # Cập nhật trạng thái của checkbox "Tự động thay đổi mắt"
        self.auto_eye = bool(self.auto_eye_var.get())
        self.toggle_eye_mode()

        # Cập nhật giá trị thời gian ghi âm từ thanh trượt
        self.recording_time_limit = self.recording_time_var.get()

        # Lưu tất cả các cài đặt vào file
        self.save_stuttering_settings()

        # Đóng cửa sổ
        window.destroy()

    def toggle_eye_mode(self):
        """Hàm bật/tắt chế độ tự động thay đổi mắt"""
        if self.auto_eye:
            self.start_random_eye_change()  # Bắt đầu thay đổi mắt ngẫu nhiên
        else:
            if self.random_eye_timer:
                self.after_cancel(self.random_eye_timer)  # Hủy timer nếu đã bật

    def on_listbox_double_click(self, event):
        """Xử lý sự kiện double-click trên listbox."""
        # Lấy mục đã được chọn trong listbox
        selection = self.corrected_listbox.curselection()
        if selection:
            selected_text = self.corrected_listbox.get(selection)

            # Loại bỏ các ký tự thừa như "[1]" trong text
            if "[" in selected_text:
                selected_text = selected_text.split("[")[0].strip()

            # Chuyển văn bản thành chuỗi nguyên âm để đồng bộ với miệng
            converted_text = self.convert_text_to_vowel_image(selected_text)

            # Phát âm văn bản và đồng bộ trạng thái miệng (mouth drawing)
            self.play_speech(selected_text, converted_text)

    def play_speech(self, text, converted_text):
        """Phát âm văn bản đã nhận diện và đồng bộ với miệng."""
        tts = gTTS(text=text, lang='vi')

        # Tạo tệp tạm thời để lưu âm thanh
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_mp3_file:
            tts.save(temp_mp3_file.name)

        # Xử lý âm thanh
        audio_segment = AudioSegment.from_file(temp_mp3_file.name)
        total_duration_ms = len(audio_segment)

        # Tách phần đã chuyển đổi thành các phần nhỏ
        converted_parts = converted_text.split(",")
        if len(converted_parts) == 0:
            print("Warning: No converted parts found.")
            return

        delay_per_part = total_duration_ms / len(converted_parts)
        temp_wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio_segment.export(temp_wav_file.name, format="wav")

        # Phát âm thanh
        pygame.mixer.music.load(temp_wav_file.name)
        pygame.mixer.music.play()

        # Đồng bộ sliders hoặc miệng với âm thanh
        self.sync_sliders_with_audio(converted_parts, delay_per_part)

        # Xóa tệp tạm
        os.remove(temp_mp3_file.name)
        os.remove(temp_wav_file.name)

    def sync_sliders_with_audio(self, converted_parts, delay_per_part):
        """Đồng bộ sliders hoặc trạng thái miệng với âm thanh."""
        for i, part in enumerate(converted_parts):
            # Đồng bộ trạng thái miệng dựa trên phần text
            self.after(int(i * delay_per_part), lambda p=part: self.setup_app.update_mouth_from_text(p))

    def on_chat_log_modified(self, event):
        """Hàm xử lý khi nội dung khung chat thay đổi"""
        if self.chat_log.edit_modified():  # Kiểm tra nếu nội dung thực sự đã thay đổi
            # Lưu nội dung hiện tại vào file
            self.save_chat_log_to_file()
            # Sau khi lưu file, cập nhật Listbox để phản ánh các thay đổi
            self.update_corrected_listbox()
            # Đặt lại cờ 'modified' để có thể kích hoạt lại sự kiện lần sau
            self.chat_log.edit_modified(False)

    def save_chat_log_to_file(self):
        """Lưu nội dung khung chat vào file .HOC hiện hành"""
        try:
            # Lưu nội dung hiện tại của khung chat vào file
            with open(self.current_hoc_file, "w", encoding='utf-8') as file:
                content = self.chat_log.get("1.0", tk.END)
                file.write(content)
                self.update_corrected_listbox()

        except FileNotFoundError:
            messagebox.showerror("Error", f"Cannot save to file {self.current_hoc_file}")

    def load_chat_log_from_file(self):
        """Nạp nội dung từ file .HOC vào khung chat và cập nhật Listbox."""
        try:
            with open(self.current_hoc_file, "r", encoding='utf-8', errors='ignore') as file:
                content = file.read()
                self.chat_log.delete("1.0", tk.END)
                self.chat_log.insert(tk.END, content)
                self.update_corrected_listbox()

        except FileNotFoundError:
            messagebox.showerror("Error", f"Cannot open file {self.current_hoc_file}")

    def update_corrected_listbox(self):
        """Cập nhật Listbox với các câu 'Corrected:' từ file .HOC, đồng thời xử lý số lần chỉnh sửa."""
        # Xóa nội dung hiện tại trong Listbox
        self.corrected_listbox.delete(0, tk.END)

        corrected_count = defaultdict(int)  # Đếm số lần câu "Corrected:" xuất hiện
        original_count = defaultdict(int)  # Đếm số lần câu "Original:" xuất hiện

        # Đọc toàn bộ nội dung file .HOC
        try:
            with open(self.current_hoc_file, "r", encoding='utf-8', errors='ignore') as file:
                lines = file.readlines()

            # Đếm số lần câu "Corrected:" và "Original:" xuất hiện
            for line in lines:
                if line.startswith("Corrected:"):
                    sentence = line.replace("Corrected:", "").strip().lower()
                    corrected_count[sentence] += 1
                elif line.startswith("Original:"):
                    sentence = line.replace("Original:", "").strip().lower()
                    original_count[sentence] += 1

            # Cập nhật listbox với các câu "Corrected:" cùng số lần xuất hiện
            for sentence, count in corrected_count.items():
                # Nếu có câu "Original" tương ứng, trừ số lần xuất hiện của nó
                final_count = count - original_count.get(sentence, 0)

                # Chỉ thêm vào listbox nếu số lần sửa là dương
                if final_count > 0:
                    display_sentence = f"{sentence} [{final_count}]"
                    self.corrected_listbox.insert(tk.END, display_sentence)

        except FileNotFoundError:
            messagebox.showerror("Error", f"Cannot open file {self.current_hoc_file}")

    def manage_hoc_files(self):
        """Mở cửa sổ quản lý file .HOC"""
        hoc_window = Toplevel(self)
        hoc_window.title("Quản lý người học)")
        hoc_window.geometry("300x300")

        # Đặt cửa sổ quản lý HOC luôn nổi trước cửa sổ chính
        hoc_window.transient(self.master)
        hoc_window.grab_set()
        hoc_window.focus_set()
        # Danh sách hiển thị các file .HOC
        self.hoc_listbox = Listbox(hoc_window)
        self.hoc_listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Thêm các file .HOC hiện có vào listbox (không hiển thị phần đuôi .HOC)
        for filename in os.listdir("."):
            if filename.endswith(".HOC"):
                self.hoc_listbox.insert(tk.END, filename[:-4])  # Loại bỏ phần .HOC

        # Nút Add để thêm file .HOC mới
        add_button = tk.Button(hoc_window, text="Add", command=self.add_hoc_file)
        add_button.pack(pady=5)

        # Nút Del để xóa file .HOC đã chọn
        del_button = tk.Button(hoc_window, text="Del", command=self.del_hoc_file)
        del_button.pack(pady=5)

        # Nút "Chọn và đóng"
        select_button = tk.Button(hoc_window, text="Chọn và đóng", command=lambda: self.select_hoc_file(hoc_window))
        select_button.pack(pady=5)

    def add_hoc_file(self):
        """Thêm file .HOC mới"""
        new_file = simpledialog.askstring("Thêm file", "Nhập tên file mới (không chứa đuôi .HOC):")
        if new_file:
            new_file_with_ext = f"{new_file}.HOC"
            if os.path.exists(new_file_with_ext):
                messagebox.showwarning("Lỗi", "File đã tồn tại!")
            else:
                # Tạo file .HOC mới
                open(new_file_with_ext, "w").close()
                self.hoc_listbox.insert(tk.END, new_file)  # Thêm file vào listbox
                messagebox.showinfo("Thành công", f"File {new_file_with_ext} đã được tạo.")

    def del_hoc_file(self):
        """Xóa file .HOC được chọn"""
        selected_index = self.hoc_listbox.curselection()
        if selected_index:
            selected_file = self.hoc_listbox.get(selected_index) + ".HOC"
            if messagebox.askyesno("Xóa file", f"Bạn có chắc muốn xóa {selected_file}?"):
                os.remove(selected_file)  # Xóa file
                self.hoc_listbox.delete(selected_index)  # Xóa khỏi listbox
                messagebox.showinfo("Thành công", f"File {selected_file} đã được xóa.")
        else:
            messagebox.showwarning("Lỗi", "Bạn chưa chọn file để xóa!")

    def select_hoc_file(self, window):
        """Chọn file .HOC và đóng cửa sổ, đồng thời load nội dung file vào khung chat"""
        selected_index = self.hoc_listbox.curselection()
        if selected_index:
            selected_file = self.hoc_listbox.get(selected_index) + ".HOC"
            self.current_hoc_file = selected_file  # Cập nhật file .HOC hiện hành

            # Load nội dung từ file .HOC và đưa vào khung chat
            self.load_chat_log_from_file()

            # Cập nhật tiêu đề ChatBox với tên file mới
            self.chatbox_frame.config(text=f"Tập luyện - ({self.current_hoc_file})",
                                      font=("Arial", 16, "bold"), labelanchor='n')

            messagebox.showinfo("Thành công", f"Đã chọn {selected_file} làm file hiện hành.")
            window.destroy()  # Đóng cửa sổ quản lý
        else:
            messagebox.showwarning("Lỗi", "Bạn chưa chọn file nào!")

    def load_chat_log_from_file(self):
        """Nạp nội dung file .HOC vào khung chat"""
        try:
            with open(self.current_hoc_file, "r", encoding='utf-8', errors='ignore') as file:
                # Xóa nội dung cũ trong khung chat
                self.chat_log.delete("1.0", tk.END)

                # Nạp nội dung mới từ file
                content = file.read()
                self.chat_log.insert(tk.END, content)
        except FileNotFoundError:
            messagebox.showerror("Lỗi", f"Không thể mở file {self.current_hoc_file}")

    def start_random_eye_change(self):
        """Hàm bắt đầu thay đổi mắt ngẫu nhiên mỗi 5 giây"""
        if self.auto_eye:
            self.change_random_eye()
            self.random_eye_timer = self.after(CHOP_MAT, self.start_random_eye_change)

    def change_random_eye(self):
        """Thay đổi ngẫu nhiên trạng thái mắt từ Eye2 đến Eye9"""
        available_eye_states = ["Eye2", "Eye3", "Eye4", "Eye5", "Eye6", "Eye7", "Eye8", "Eye9"]
        random_eye = random.choice(available_eye_states)

        # Đặt về trạng thái Eye1 sau 500ms
        def reset_to_eye1():
            self.change_eye_state("Eye1")

        # Chuyển sang trạng thái mắt ngẫu nhiên
        self.change_eye_state(random_eye)

        # Thời gian ngẫu nhiên từ 300ms đến 1000ms để chuyển về Eye1
        random_delay = random.randint(500, 1000)  # Chọn thời gian ngẫu nhiên giữa 300 và 1000ms

        # Sau khoảng thời gian ngẫu nhiên, chuyển về Eye1
        self.after(random_delay, reset_to_eye1)

    def change_eye_state(self, eye_state):
        """Hàm thay đổi trạng thái mắt và cập nhật slider"""
        self.current_eye_state = eye_state
        listbox = self.setup_app.listbox_eye

        # Kiểm tra nếu eye_state có trong listbox
        try:
            eye_index = listbox.get(0, tk.END).index(eye_state)
        except ValueError:
            print(f"Warning: Eye state '{eye_state}' not found in listbox. Skipping change.")
            return

        # Xóa lựa chọn hiện tại và chọn trạng thái mắt mới
        listbox.select_clear(0, tk.END)
        listbox.select_set(eye_index)
        listbox.event_generate("<<ListboxSelect>>")

        # Cập nhật sliders và vẽ lại đôi mắt
        self.setup_app.on_eye_select(None)

    def clean_chat_log_before_save(self):
        """Xóa các dòng không cần thiết khỏi chat log trước khi lưu vào file .HOC"""
        # Lấy toàn bộ nội dung từ chat log
        chat_log_content = self.chat_log.get("1.0", tk.END).splitlines()

        # Danh sách các dòng không cần thiết
        unwanted_lines = ["Listening...", "Sorry, I couldn't understand the audio."]

        # Xử lý các dòng, giữ lại các dòng không nằm trong unwanted_lines và không rỗng
        filtered_lines = [line for line in chat_log_content if line.strip() and line not in unwanted_lines]

        # Xóa nội dung hiện tại của chat log
        self.chat_log.delete("1.0", tk.END)

        # Chèn lại các dòng đã lọc
        for line in filtered_lines:
            self.chat_log.insert(tk.END, line + "\n")

        # Cuộn đến cuối cùng
        self.chat_log.see(tk.END)

    def recognize_speech(self):
        """Nhận dạng giọng nói và xử lý kết quả"""
        recognizer = sr.Recognizer()
        positive_feedback = ["bạn đã làm rất tốt", "tuyệt vời"]

        with sr.Microphone() as source:
            self.chat_log.insert(tk.END, "Listening...\n")
            self.chat_log.see(tk.END)  # Đảm bảo chatbox cuộn đến dòng cuối
            # Lấy giá trị thời gian ghi âm từ thanh trượt
            phrase_time_limit = self.recording_time_limit
            audio = recognizer.listen(source, phrase_time_limit=phrase_time_limit)

        try:
            # Nhận diện giọng nói
            text = recognizer.recognize_google(audio, language="vi-VN")
            self.chat_log.insert(tk.END, f"Original: {text}\n")

            # Chỉnh sửa câu nếu phát hiện lắp bắp
            corrected_text = self.fix_stuttering(text)

            # Trước khi lưu, làm sạch các dòng không cần thiết
            self.clean_chat_log_before_save()

            # Ghi câu gốc và câu corrected vào file
            with open(self.current_hoc_file, "a", encoding='utf-8', errors='ignore') as file:
                file.write(f"Original: {text}\nCorrected: {corrected_text}\n")

            if corrected_text.lower() != text.lower():
                # Nếu có chỉnh sửa, thêm vào chat_log và cập nhật listbox
                final_text = f"Bạn muốn nói là: {corrected_text}"
                self.chat_log.insert(tk.END, f"Corrected: {corrected_text}\n")
                self.consecutive_correct = 0

                # Đếm câu sai và cập nhật listbox
                self.track_sentence(corrected_text, False)
                self.update_corrected_listbox()  # Cập nhật listbox sau khi ghi vào file
            else:
                # Nếu không có chỉnh sửa, cung cấp phản hồi tích cực nếu đạt số lượng câu đúng liên tiếp
                self.consecutive_correct += 1
                if self.consecutive_correct >= 3:
                    final_text = random.choice(positive_feedback)
                else:
                    final_text = corrected_text

                # Đếm câu đúng và cập nhật listbox
                self.track_sentence(corrected_text, True)
                self.update_corrected_listbox()  # Cập nhật listbox sau khi ghi vào file

            # Phát âm câu đã nhận diện hoặc phản hồi
            converted_text = self.convert_text_to_vowel_image(final_text)
            threading.Thread(target=self.play_speech, args=(final_text, converted_text)).start()

        except sr.UnknownValueError:
            self.chat_log.insert(tk.END, "Sorry, I couldn't understand the audio.\n")
        except sr.RequestError as e:
            self.chat_log.insert(tk.END, f"API unavailable: {e}\n")

        # Luôn cuộn đến nội dung mới nhất
        self.chat_log.see(tk.END)

    def play_speech(self, text, converted_text):
        """Phát âm giọng nói đã nhận diện"""
        tts = gTTS(text=text, lang='vi')

        # Tạo tệp tạm thời để lưu âm thanh
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_mp3_file:
            tts.save(temp_mp3_file.name)

        # Xử lý âm thanh
        audio_segment = AudioSegment.from_file(temp_mp3_file.name)
        total_duration_ms = len(audio_segment)

        converted_parts = converted_text.split(",")
        if len(converted_parts) == 0:
            print("Warning: No converted parts found.")
            return

        delay_per_part = total_duration_ms / len(converted_parts)
        #temp_wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        #audio_segment.export(temp_wav_file.name, format="wav")

        #audioWavTam = 'H:\\DuAn\\NCKH Hocsinh\\Hung_KhuonMat\\App\\audioWavTam.wav'
        audio_segment.export(audioWavTam, format="wav")
        #temp_wav_file.close()  # Đảm bảo file được đóng
        # Khởi động Pygame
        pygame.mixer.init()
        pygame.mixer.music.load(audioWavTam)
        #pygame.mixer.music.load(file_path)
        # pygame.mixer.music.set_volume(self.volume_slider.get())
        pygame.mixer.music.play()

        # Đồng bộ sliders với âm thanh
        self.sync_sliders_with_audio(converted_parts, delay_per_part)

        # Đợi cho đến khi âm thanh phát xong
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)  # Chờ một chút
        # Dừng âm thanh
        pygame.mixer.music.stop()
        time.sleep(0.1)
        pygame.mixer.quit()
        # Xóa tệp tạm
        os.remove(audioWavTam)
        os.remove(temp_mp3_file.name)
        #os.remove(temp_wav_file.name)

    def sync_sliders_with_audio(self, converted_parts, delay_per_part):
        """Đồng bộ sliders với âm thanh"""
        for i, part in enumerate(converted_parts):
            self.after(int(i * delay_per_part), lambda p=part: self.setup_app.update_sliders_from_text_trans(p))

    def track_sentence(self, text, is_correct):
        """Hàm theo dõi và đếm số lượng câu đúng và câu sai."""
        self.total_sentences += 1
        if is_correct:
            self.correct_sentences += 1
        else:
            cleaned_text = text.strip().lower()
            if cleaned_text in self.wrong_sentences:
                self.wrong_sentences[cleaned_text] += 1
            else:
                self.wrong_sentences[cleaned_text] = 1

    def analyze_chat(self):
        """Phân tích chat log từ hộp chat."""
        chat_log_content = self.chat_log.get("1.0", tk.END).strip()

        if not chat_log_content:
            return

        feedback = f"Bạn đã nói {self.total_sentences} câu, trong đó {self.correct_sentences} câu chính xác.\n"

        if self.wrong_sentences:
            feedback += "Bạn đã nói sai các câu:\n"
            for sentence, count in self.wrong_sentences.items():
                feedback += f"- {sentence} (nói sai {count} lần)\n"
        else:
            feedback += "Bạn không có câu nào sai."

        self.chat_log.insert(tk.END, feedback + "\n")
        self.chat_log.see(tk.END)

        # Phát âm phản hồi phân tích
        threading.Thread(target=self.play_speech, args=(feedback, self.convert_text_to_vowel_image(feedback))).start()

    def convert_text_to_vowel_image(self, text_trans):
        """Chuyển đổi văn bản thành chuỗi hình ảnh nguyên âm cho phát âm"""
        replacements = {
            'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a', 'ă': 'ă', 'ằ': 'ă', 'ắ': 'ă', 'ẳ': 'ă', 'ẵ': 'ă',
            'ặ': 'ă',
            'â': 'â', 'ầ': 'â', 'ấ': 'â', 'ẩ': 'â', 'ẫ': 'â', 'ậ': 'â', 'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e',
            'ẹ': 'e',
            'ê': 'ê', 'ề': 'ê', 'ế': 'ê', 'ể': 'ê', 'ễ': 'ê', 'ệ': 'ê', 'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i',
            'ị': 'i',
            'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o', 'ô': 'ô', 'ồ': 'ô', 'ố': 'ô', 'ổ': 'ô', 'ỗ': 'ô',
            'ộ': 'ô',
            'ơ': 'ơ', 'ờ': 'ơ', 'ớ': 'ơ', 'ở': 'ơ', 'ỡ': 'ơ', 'ợ': 'ơ', 'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u',
            'ụ': 'u',
            'ư': 'ư', 'ừ': 'ư', 'ứ': 'ư', 'ử': 'ư', 'ữ': 'ư', 'ự': 'ư', 'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y',
            'ỵ': 'y',
            'đ': 'd'
        }
        vowel_to_image = {
            "a": "A0", "ă": "AW", "â": "AA", "e": "E0", "ê": "EE", "i": "IY", "y": "IY", "o": "O0", "ô": "OO",
            "ơ": "OW", "u": "U0", "ư": "UW", " ": "DF"
        }

        text_without_diacritics = ''.join(replacements.get(c, c) for c in text_trans.lower())
        vowel_images = [vowel_to_image.get(c) for c in text_without_diacritics if c in vowel_to_image]
        converted_text = ','.join(vowel_images) + ",DF"

        return converted_text

    def fix_stuttering(self, text):
        """Hàm xử lý lặp từ (lắp bắp) dựa trên danh sách các từ đặc biệt"""
        lower_text = text.lower()
        words = lower_text.split()
        corrected_words = []
        i = 0

        while i < len(words):
            word = words[i]
            found_phrase = False

            if self.special_word_check:
                for phrase in self.allowed_phrases:
                    phrase_words = phrase.split()
                    if words[i:i + len(phrase_words)] == phrase_words:
                        corrected_words.extend(phrase_words)
                        i += len(phrase_words)
                        found_phrase = True
                        break

            if not found_phrase:
                if not (i > 0 and word == words[i - 1]):
                    corrected_words.append(word)
                i += 1

        corrected_text = ' '.join(corrected_words)
        return corrected_text

    def load_stuttering_settings(self):
        """Load cài đặt từ lắp bắp và trạng thái tự động thay đổi mắt từ file"""
        try:
            with open(STUTTER_FILE, "r", encoding='utf-8', errors='ignore') as file:
                lines = file.readlines()
                if len(lines) > 0:
                    # Đọc giá trị từ dòng đầu tiên
                    settings = lines[0].strip().split(',')
                    self.special_word_check = bool(int(settings[0]))  # Giá trị thứ nhất là trạng thái của từ đặc biệt
                    self.auto_eye = bool(int(settings[1]))  # Giá trị thứ hai là trạng thái của "Tự động thay đổi mắt"
                    self.recording_time_limit = int(settings[2])  # Giá trị thứ ba là thời gian ghi âm

                # Đọc các từ đặc biệt từ dòng tiếp theo
                self.allowed_phrases = [line.strip() for line in lines[1:]]
        except FileNotFoundError:
            # Mặc định nếu file không tồn tại
            self.special_word_check = True
            self.auto_eye = False  # Mặc định là tắt chế độ tự động thay đổi mắt
            self.recording_time_limit = 5  # Mặc định thời gian ghi âm là 5 giây
            self.allowed_phrases = ["luôn luôn", "thường thường", "ngày ngày", "đêm đêm"]

    def save_stuttering_settings(self):
        """Lưu cài đặt từ lắp bắp và trạng thái tự động thay đổi mắt vào file"""
        with open(STUTTER_FILE, "w") as file:
            # Ghi trạng thái của từ đặc biệt, tự động thay đổi mắt, và thời gian ghi âm trên dòng đầu tiên
            file.write(f"{int(self.special_word_check)},{int(self.auto_eye)},{self.recording_time_limit}\n")

            # Ghi các từ đặc biệt vào các dòng tiếp theo
            for phrase in self.allowed_phrases:
                file.write(phrase + "\n")

    def add_phrase(self):
        """Thêm cụm từ mới vào danh sách từ lắp bắp"""
        new_phrase = simpledialog.askstring("Add Phrase", "Enter a new phrase:")
        if new_phrase and new_phrase not in self.allowed_phrases:
            self.allowed_phrases.append(new_phrase)
            self.phrase_listbox.insert(tk.END, new_phrase)

    def delete_phrase(self):
        """Xóa cụm từ khỏi danh sách từ lắp bắp"""
        selected_index = self.phrase_listbox.curselection()
        if selected_index:
            phrase = self.phrase_listbox.get(selected_index)
            self.allowed_phrases.remove(phrase)
            self.phrase_listbox.delete(selected_index)


class ArduinoConnection:
    """Handles communication with Arduino."""

    def __init__(self):
        self.serial_connection = None
        self.is_connected = False
        self.connect_button = None

    def update_port_list(self, combobox):
        try:
            ports = [port.device for port in serial.tools.list_ports.comports()]
        except AttributeError:
            ports = [port for port in serial.Serial.list_ports.comports()]
        combobox['values'] = ports
        if ports:
            combobox.current(0)

    def connect_to_arduino(self, port, connect_button):
        try:
            self.serial_connection = serial.Serial(port, 9600)
            self.is_connected = True
            connect_button.config(text="Disconnect")
        except serial.SerialException as e:
            messagebox.showerror("Error", f"Error connecting to Arduino: {e}")

    def disconnect_from_arduino(self, connect_button):
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
            self.is_connected = False
            connect_button.config(text="Connect")

    def send_data(self, data):
        if self.is_connected and self.serial_connection:
            try:
                formatted_data = ','.join(map(str, map(int, data)))
                self.serial_connection.write(f"{formatted_data}\n".encode())
            except serial.SerialException as e:
                messagebox.showerror("Error", f"Error sending data to Arduino: {e}")

    def toggle_connection(self, connect_button, root):
        self.connect_button = connect_button
        if self.is_connected:
            self.disconnect_from_arduino(connect_button)
        else:
            self.show_port_selector(root)

    def show_port_selector(self, root):
        popup = Toplevel(root)
        popup.title("Select Port")
        popup.transient(root)
        popup.grab_set()

        port_combobox = ttk.Combobox(popup)
        port_combobox.grid(row=0, column=0, padx=5, pady=5)
        self.update_port_list(port_combobox)

        ok_button = ttk.Button(popup, text="OK", command=lambda: self.select_port(popup, port_combobox))
        ok_button.grid(row=1, column=0, pady=1)

        root.wait_window(popup)

    def select_port(self, popup, port_combobox):
        port = port_combobox.get()
        if not port:
            messagebox.showerror("Error", "No serial port selected.")
            return

        self.connect_to_arduino(port, self.connect_button)
        popup.destroy()

class ImageManager:
    def __init__(self):
        # Tạo một từ điển để lưu trữ các hình ảnh
        self.images = {}

        # Đường dẫn tới thư mục hiện hành
        self.current_dir = os.getcwd()

        # Tải tất cả các hình ảnh cần thiết
        self.load_image("add", "I_Add.png")
        self.load_image("new", "I_new.png")
        self.load_image("play", "I_play.png")
        self.load_image("pause", "I_pause.png")
        self.load_image("load", "I_load.png")
        self.load_image("analyze", "I_analyze.png")
        self.load_image("copy", "I_copy.png")
        self.load_image("delete", "I_delete.png")
        self.load_image("mic", "I_mic.png")
        self.load_image("open", "I_open.png")
        self.load_image("option", "I_option.png")
        self.load_image("paste", "I_paste.png")
        self.load_image("rename", "I_rename.png")
        self.load_image("save", "I_save.png")
        self.load_image("use", "I_use.png")
        self.load_image("reset", "I_reset.png")
        self.load_image("connect", "I_connect.png")
        self.load_image("up", "I_up.png")
        self.load_image("down", "I_down.png")

    def load_image(self, key, file_path, size=(30, 30)):  # Giảm kích thước ảnh
        """Tải ảnh từ file và lưu trữ trong dictionary với kích thước tùy chọn"""
        try:
            image = Image.open(file_path).resize(size, Image.Resampling.LANCZOS)  # Sử dụng LANCZOS thay vì ANTIALIAS
            self.images[key] = ImageTk.PhotoImage(image)
        except Exception as e:
            print(f"Error loading image {file_path}: {e}")

    def get_image(self, key):
        """Trả về ảnh tương ứng với key đã lưu"""
        return self.images.get(key, None)
    
class SliderManager:
    """Manages slider creation and resetting for mouth and eyes."""

    def __init__(self, root, vars, update_callback):
        self.root = root
        self.vars = vars
        self.update_callback = update_callback
        self.sliders = []

    def create_slider(self, label_text, slide_num, row, column, frame):
        min_val, max_val, step = SLIDE_VALUES[slide_num]
        label = tk.Label(frame, text=label_text)
        label.grid(row=row, column=column, sticky='w')
        slider = tk.Scale(frame, from_=min_val, to=max_val, orient=tk.HORIZONTAL,
                          resolution=step, variable=self.vars[slide_num], command=self.update_callback)
        slider.grid(row=row, column=column + 1, )
        self.sliders.append(slider)

    def reset_mouth_sliders(self):
        for slide_num in range(1, 9):
            default_value = 5 if slide_num in [1, 2, 3, 4, 5, 6] else 1
            self.vars[slide_num].set(default_value)
        self.update_callback()

    def reset_eye_sliders(self):
        for slide_num in range(9, 16):
            default_value = 5 if slide_num in [9, 10, 11, 12, 15] else 1
            self.vars[slide_num].set(default_value)
        self.update_callback()

    def reset_sliders(self):
        self.reset_mouth_sliders()
        self.reset_eye_sliders()


class EyeDrawer:
    """Handles drawing eyes and nose on the canvas."""

    def __init__(self, canvas, vars):
        self.canvas = canvas
        self.vars = vars

    def draw_eyes(self):
        self.draw_eye(130, 180, self.vars[9].get() * 4, self.vars[10].get() * 4, self.vars[13].get() * EYELID_HEIGHT,
                      self.vars[15].get() - 1, is_left=True)
        self.draw_eye(270, 180, self.vars[11].get() * 4, self.vars[12].get() * 4, self.vars[14].get() * EYELID_HEIGHT,
                      self.vars[15].get() - 1, is_left=False)

    def draw_eye(self, eye_x, eye_y, pupil_x, pupil_y, eyelid_control, eyebrow_angle, is_left):
        self.canvas.create_oval(eye_x - EYE_RADIUS, eye_y - EYE_RADIUS, eye_x + EYE_RADIUS, eye_y + EYE_RADIUS,
                                fill="white", outline="orange")

        self.canvas.create_oval(eye_x - PUPIL_RADIUS - pupil_x + 20, eye_y - PUPIL_RADIUS - pupil_y + 20,
                                eye_x + PUPIL_RADIUS - pupil_x + 20, eye_y + PUPIL_RADIUS - pupil_y + 20, fill="black",
                                outline="black")

        self.canvas.create_line(eye_x - EYE_RADIUS, eye_y - EYE_RADIUS + eyelid_control / 2 - 23,
                                eye_x + EYE_RADIUS + 2, eye_y - EYE_RADIUS + eyelid_control / 2 - 23, fill="peachpuff",
                                width=55)
        self.canvas.create_line(eye_x - EYE_RADIUS, eye_y + EYE_RADIUS - eyelid_control / 2 + 23,
                                eye_x + EYE_RADIUS + 2, eye_y + EYE_RADIUS - eyelid_control / 2 + 23, fill="peachpuff",
                                width=55)

        if is_left:
            self.canvas.create_line(eye_x - EYE_RADIUS,
                                    eye_y - EYE_RADIUS + 10 + eyelid_control / 2 - eyebrow_angle * 4,
                                    eye_x + EYE_RADIUS, eye_y - EYE_RADIUS - 10 + eyelid_control / 2, fill="brown",
                                    width=10)
        else:
            self.canvas.create_line(eye_x - EYE_RADIUS, eye_y - EYE_RADIUS - 10 + eyelid_control / 2,
                                    eye_x + EYE_RADIUS,
                                    eye_y - EYE_RADIUS + 10 + eyelid_control / 2 - eyebrow_angle * 4,
                                    fill="brown", width=10)

    def draw_nose(self):
        self.canvas.create_arc(170, 210, 230, 270, start=30, extent=120, outline="orange", fill="orange", width=2)


class MouthDrawer:
    """Handles drawing mouth on the canvas."""

    def __init__(self, canvas, vars):
        self.canvas = canvas
        self.vars = vars

    def draw_mouth(self):
        self.draw_tongue()
        self.draw_teeth()
        self.draw_lips()

    def draw_lips(self):
        jaw_movement = self.vars[7].get() * 8
        upper_center_y = -self.vars[1].get() * 2 + 288
        lower_center_y = self.vars[2].get() * 2 + 300

        left_x = 2 * (self.vars[3].get() - 1) + 2 * (self.vars[5].get() - 1) + 100
        left_y = 2 * (self.vars[3].get() - 1) - 2 * (self.vars[5].get() - 1) + 295

        right_x = -(2 * (self.vars[4].get() - 1) + 2 * (self.vars[6].get() - 1)) + 300
        right_y = -(2 * (self.vars[4].get() - 1) - 2 * (self.vars[6].get() - 1)) + 295

        middle_left_x = 150
        middle_right_x = 250
        upper_lip_y = upper_center_y
        lower_lip_y = lower_center_y + jaw_movement / 2

        self.canvas.create_line(left_x, left_y, middle_left_x, upper_lip_y, middle_right_x, upper_lip_y, right_x,
                                right_y, width=23, fill="red")
        self.canvas.create_line(left_x, left_y, middle_left_x + 15, lower_lip_y, middle_right_x - 15, lower_lip_y,
                                right_x, right_y, width=23, fill="red")
        self.canvas.create_oval(left_x - 15, left_y - 15, left_x + 15, left_y + 15, fill="red", outline='')
        self.canvas.create_oval(right_x - 15, right_y - 15, right_x + 15, right_y + 15, fill="red", outline='')

    def draw_tongue(self):
        tongue_base_y = -(self.vars[8].get() - (self.vars[7].get() / 2)) * 3 + 308
        tongue_height = 25
        self.canvas.create_oval(150, tongue_base_y - tongue_height / 2, 250, tongue_base_y + tongue_height / 2,
                                fill="brown", outline='')

    def draw_teeth(self):
        upper_teeth_y = 280
        lower_teeth_y = 290 + (self.vars[7].get() / 2) * 10
        self.canvas.create_rectangle(160, upper_teeth_y, 240, upper_teeth_y + 20, fill="white")
        self.canvas.create_rectangle(160, lower_teeth_y - 10, 240, lower_teeth_y + 10, fill="white")


class ScenarioApp:
    def __init__(self, root, slider_manager, app):
        self.root = root
        self.slider_manager = slider_manager
        self.app = app

        try:
            pygame.mixer.init()
        except pygame.error as e:
            messagebox.showerror("Lỗi", f"Không thể khởi tạo pygame.mixer: {e}")
            return

        self.scenario_data = []
        self.current_file_path = "Default.KB"
        self.music_file = None
        self.playing = False
        self.current_step_index = 0
        self.copy_data = []

        self.scenario_frame = tk.LabelFrame(self.root, text="Kịch bản",  font=("Arial", 16, "bold"), labelanchor='n')
        self.scenario_frame.grid(row=0, column=2, padx=0, pady=10)

        self.create_top_buttons()
        self.create_listbox()
        self.create_bottom_buttons()
        self.create_speed_slider()

        self.open_scenario(self.current_file_path)

    def play_pause_scenario(self):
        if self.playing:
            self.playing = False
            pygame.mixer.music.pause()
            self.update_play_button_label("PLAY")
        else:
            self.playing = True
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.unpause()
            else:
                self.current_step_index = self.listbox_scenario.curselection()[
                    0] if self.listbox_scenario.curselection() else 0
                self.check_and_play_music(start_from_listbox=True)
                self.schedule_next_step()

            self.update_play_button_label("PAUSE")

    def check_and_play_music(self, start_from_listbox=False):
        if self.current_file_path:
            kb_file_name = os.path.splitext(os.path.basename(self.current_file_path))[0]
            mp3_file = f"{kb_file_name}.mp3"
            if os.path.exists(mp3_file):
                self.music_file = mp3_file
                try:
                    pygame.mixer.music.load(self.music_file)
                    if start_from_listbox:
                        start_time = (self.current_step_index * self.speed_slider.get()) / 1000
                        pygame.mixer.music.play(start=round(start_time))
                    else:
                        pygame.mixer.music.play()

                    self.root.after(100, self.check_music_status)
                except pygame.error as e:
                    messagebox.showerror("Lỗi", f"Không thể phát tệp nhạc: {e}")
            else:
                messagebox.showwarning("Cảnh báo", f"Không tìm thấy tệp MP3 tương ứng với '{kb_file_name}'")

    def create_top_buttons(self):
        # Nút NEW với hình ảnh
        button_new = tk.Button(
            self.scenario_frame,
            text="NEW",
            command=self.new_scenario,
            image=self.app.image_manager.get_image("new"),  # Key là "new"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        button_new.grid(row=0, column=0)

        # Nút LOAD với hình ảnh
        button_load = tk.Button(
            self.scenario_frame,
            text="LOAD",
            command=self.load_scenario,
            image=self.app.image_manager.get_image("load"),  # Key là "load"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        button_load.grid(row=0, column=1)

    def create_bottom_buttons(self):
        # Nút ADD với hình ảnh
        button_add = tk.Button(
            self.scenario_frame,
            text="ADD",
            command=self.add_step,
            image=self.app.image_manager.get_image("add"),  # Key là "add"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        button_add.grid(row=0, column=2)

        # Nút SAVE với hình ảnh
        button_save = tk.Button(
            self.scenario_frame,
            text="SAVE",
            command=self.save_step,
            image=self.app.image_manager.get_image("save"),  # Key là "save"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        button_save.grid(row=0, column=3)

        # Nút DELETE với hình ảnh
        button_delete = tk.Button(
            self.scenario_frame,
            text="DELETE",
            command=self.delete_selected,
            image=self.app.image_manager.get_image("delete"),  # Key là "delete"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        button_delete.grid(row=0, column=4)

        # Nút UP với hình ảnh
        button_up = tk.Button(
            self.scenario_frame,
            text="UP",
            command=self.move_up,
            image=self.app.image_manager.get_image("up"),  # Key là "up"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        button_up.grid(row=0, column=5)

        # Nút DOWN với hình ảnh
        button_down = tk.Button(
            self.scenario_frame,
            text="DOWN",
            command=self.move_down,
            image=self.app.image_manager.get_image("down"),  # Key là "down"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        button_down.grid(row=0, column=6)

        # Nút COPY với hình ảnh
        button_copy = tk.Button(
            self.scenario_frame,
            text="COPY",
            command=self.copy_step,
            image=self.app.image_manager.get_image("copy"),  # Key là "copy"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        button_copy.grid(row=0, column=7)

        # Nút PASTE với hình ảnh
        button_paste = tk.Button(
            self.scenario_frame,
            text="PASTE",
            command=self.paste_step,
            image=self.app.image_manager.get_image("paste"),  # Key là "paste"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        button_paste.grid(row=0, column=8)

        # Nút PLAY với hình ảnh
        self.button_play = tk.Button(
            self.scenario_frame,
            text="PLAY",
            command=self.play_pause_scenario,
            image=self.app.image_manager.get_image("play"),  # Key là "play"
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        self.button_play.grid(row=0, column=2)

    def create_listbox(self):
        self.listbox_frame = tk.Frame(self.scenario_frame)
        self.listbox_frame.grid(row=1, column=0, columnspan=5)

        self.scrollbar = Scrollbar(self.listbox_frame, orient="vertical")
        self.scrollbar.pack(side="right", fill="y")

        self.listbox_scenario = Listbox(self.listbox_frame, height=5, width=20, selectmode=tk.EXTENDED,
                                        yscrollcommand=self.scrollbar.set)
        self.listbox_scenario.pack(side="left", fill="both")
        self.scrollbar.config(command=self.listbox_scenario.yview)

        self.listbox_scenario.bind("<<ListboxSelect>>", self.on_listbox_select)
        self.listbox_scenario.bind("<Up>", self.on_key_press)
        self.listbox_scenario.bind("<Down>", self.on_key_press)

    def create_speed_slider(self):
        self.speed_slider = tk.Scale(self.scenario_frame, from_=100, to=500, orient='horizontal', label="Speed (ms)",
                                     resolution=100, length=160)
        self.speed_slider.set(200)
        self.speed_slider.grid(row=1, column=6, columnspan=5)

    def new_scenario(self):
        new_window = Toplevel(self.root)
        new_window.title("Tạo file kịch bản mới")

        tk.Label(new_window, text="Nhập tên file mới (.KB sẽ được thêm tự động):").pack(pady=10)
        file_name_entry = tk.Entry(new_window)
        file_name_entry.pack()

        def create_file():
            file_name = file_name_entry.get().strip()
            if not file_name:
                messagebox.showerror("Lỗi", "Tên tệp không được để trống")
                return

            file_name_with_ext = f"{file_name}.KB"
            if os.path.exists(file_name_with_ext):
                messagebox.showwarning("Cảnh báo", f"Tệp '{file_name_with_ext}' đã tồn tại!")
            else:
                with open(file_name_with_ext, 'w') as f:
                    pass
                messagebox.showinfo("Thành công", f"Tệp '{file_name_with_ext}' đã được tạo thành công!")
                new_window.destroy()

                self.current_file_path = file_name_with_ext
                self.scenario_data = []
                self.listbox_scenario.delete(0, tk.END)
                self.update_scenario_frame_title()

        tk.Button(new_window, text="Tạo", command=create_file).pack(pady=10)

    def load_scenario(self):
        load_window = Toplevel(self.root)
        load_window.title("Mở kịch bản")

        tk.Label(load_window, text="Chọn tệp .KB:").pack(pady=10)

        listbox_files = Listbox(load_window, height=10, width=40)
        listbox_files.pack(pady=10)

        kb_files = [f for f in os.listdir() if f.endswith(".KB")]
        for f in kb_files:
            listbox_files.insert(tk.END, f)

        def load_selected_file():
            selection = listbox_files.curselection()
            if selection:
                selected_file = listbox_files.get(selection[0])
                if selected_file == os.path.basename(self.current_file_path):
                    messagebox.showinfo("Thông báo", f"Tệp '{selected_file}' đã được mở.")
                else:
                    self.open_scenario(selected_file)
                    load_window.destroy()

        tk.Button(load_window, text="Mở", command=load_selected_file).pack(pady=10)
        tk.Button(load_window, text="Đóng", command=load_window.destroy).pack()

    def update_scenario_frame_title(self):
        file_name = os.path.basename(self.current_file_path)
        self.scenario_frame.config(text=f"Kịch bản {file_name}")

    def open_scenario(self, file_path):
        self.current_file_path = file_path
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                self.scenario_data = [list(map(int, line.strip().split(','))) for line in lines]

            self.listbox_scenario.delete(0, tk.END)
            for step in self.scenario_data:
                self.listbox_scenario.insert(tk.END, ','.join(map(str, step)))

            if self.listbox_scenario.size() > 0:
                self.listbox_scenario.select_set(0)
                self.on_listbox_select(None)

            self.update_scenario_frame_title()

        except FileNotFoundError:
            messagebox.showerror("Lỗi", f"Tệp '{file_path}' không tồn tại.")

    def play_pause_scenario(self):
        if self.playing:
            self.playing = False
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
            self.update_play_button_label("PLAY")
        else:
            self.playing = True
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.unpause()
            else:
                self.current_step_index = self.listbox_scenario.curselection()[
                    0] if self.listbox_scenario.curselection() else 0
                self.check_and_play_music(start_from_listbox=True)
                self.schedule_next_step()

            self.update_play_button_label("PAUSE")

    def check_and_play_music(self, start_from_listbox=False):
        if self.current_file_path:
            kb_file_name = os.path.splitext(os.path.basename(self.current_file_path))[0]
            mp3_file = f"{kb_file_name}.mp3"
            if os.path.exists(mp3_file):
                self.music_file = mp3_file
                try:
                    pygame.mixer.music.load(self.music_file)
                    if start_from_listbox:
                        speed_ms = self.speed_slider.get()
                        start_time = (self.current_step_index * speed_ms) / 1000
                        pygame.mixer.music.play(start=round(start_time))
                    else:
                        pygame.mixer.music.play()

                    self.root.after(100, self.check_music_status)
                except pygame.error as e:
                    messagebox.showerror("Lỗi", f"Không thể phát tệp nhạc: {e}")
            else:
                messagebox.showwarning("Cảnh báo", f"Không tìm thấy tệp MP3 tương ứng với '{kb_file_name}'")

    def check_music_status(self):
        if not pygame.mixer.music.get_busy():
            self.playing = False
            self.update_play_button_label("PLAY")
        else:
            self.root.after(100, self.check_music_status)

    def update_play_button_label(self, text):
        self.button_play.config(text=text)

    def schedule_next_step(self):
        if not self.playing or self.current_step_index >= len(self.scenario_data):
            self.playing = False
            pygame.mixer.music.stop()
            return

        self.listbox_scenario.select_clear(0, tk.END)
        self.listbox_scenario.select_set(self.current_step_index)
        self.listbox_scenario.see(self.current_step_index)
        self.listbox_scenario.event_generate("<<ListboxSelect>>")

        self.current_step_index += 1

        if self.playing and self.current_step_index < len(self.scenario_data):
            speed = self.speed_slider.get()
            self.root.after(speed, self.schedule_next_step)
        else:
            self.playing = False
            pygame.mixer.music.stop()

    def add_step(self):
        current_slider_values = [int(self.slider_manager.vars[i].get()) for i in range(1, 17)]
        selection = self.listbox_scenario.curselection()
        if selection:
            index = selection[-1] + 1
        else:
            index = len(self.scenario_data)

        self.scenario_data.insert(index, current_slider_values)
        self.listbox_scenario.insert(index, ','.join(map(str, current_slider_values)))
        self.listbox_scenario.select_set(index)

    def save_scenario(self):
        try:
            with open(self.current_file_path, 'w') as f:
                for step in self.scenario_data:
                    f.write(','.join(map(str, step)) + '\n')
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu kịch bản: {e}")

    def save_step(self):
        selection = self.listbox_scenario.curselection()
        if selection:
            index = selection[0]
            current_slider_values = [int(self.slider_manager.vars[i].get()) for i in range(1, 17)]
            self.scenario_data[index] = current_slider_values

            self.listbox_scenario.delete(index)
            self.listbox_scenario.insert(index, ','.join(map(str, current_slider_values)))

            self.save_scenario()
        else:
            messagebox.showwarning("Cảnh báo", "Không có bước nào được chọn để lưu.")

    def delete_selected(self):
        selection = self.listbox_scenario.curselection()
        if selection:
            for index in reversed(selection):
                del self.scenario_data[index]
                self.listbox_scenario.delete(index)
            self.save_scenario()

    def move_up(self):
        selection = self.listbox_scenario.curselection()
        if selection:
            for i in selection:
                if i > 0:
                    self.scenario_data[i], self.scenario_data[i - 1] = self.scenario_data[i - 1], self.scenario_data[i]

            self.update_listbox()
            new_selection = [i - 1 for i in selection if i > 0]
            self.listbox_scenario.select_set(*new_selection)
            self.save_scenario()

    def move_down(self):
        selection = self.listbox_scenario.curselection()
        if selection:
            for i in reversed(selection):
                if i < len(self.scenario_data) - 1:
                    self.scenario_data[i], self.scenario_data[i + 1] = self.scenario_data[i + 1], self.scenario_data[i]

            self.update_listbox()
            new_selection = [i + 1 for i in selection if i < len(self.scenario_data) - 1]
            self.listbox_scenario.select_set(*new_selection)
            self.save_scenario()

    def copy_step(self):
        selection = self.listbox_scenario.curselection()
        if selection:
            self.copy_data = [self.scenario_data[i] for i in selection]

    def paste_step(self):
        if self.copy_data:
            selection = self.listbox_scenario.curselection()
            if selection:
                index = selection[-1] + 1
            else:
                index = len(self.scenario_data)

            for step in self.copy_data:
                self.scenario_data.insert(index, step)
                self.listbox_scenario.insert(index, ','.join(map(str, step)))
                index += 1

            self.save_scenario()

    def on_listbox_select(self, event):
        selection = self.listbox_scenario.curselection()
        if selection:
            index = selection[0]
            selected_step = self.scenario_data[index]
            self.update_sliders(selected_step)

    def update_sliders(self, step_values):
        for i, value in enumerate(step_values, start=1):
            self.slider_manager.vars[i].set(value)
        self.app.draw_mouth_and_eyes()
        self.app.send_data_to_arduino()

    def update_listbox(self):
        self.listbox_scenario.delete(0, tk.END)
        for step in self.scenario_data:
            self.listbox_scenario.insert(tk.END, ','.join(map(str, step)))

    def on_key_press(self, event):
        selection = self.listbox_scenario.curselection()
        if not selection:
            return

        index = selection[0]

        if event.keysym == "Up" and index > 0:
            new_index = index - 1
            self.listbox_scenario.select_clear(0, tk.END)
            self.listbox_scenario.select_set(new_index)
            self.listbox_scenario.event_generate("<<ListboxSelect>>")
        elif event.keysym == "Down" and index < self.listbox_scenario.size() - 1:
            new_index = index + 1
            self.listbox_scenario.select_clear(0, tk.END)
            self.listbox_scenario.select_set(new_index)
            self.listbox_scenario.event_generate("<<ListboxSelect>>")



class KaraokeFrame(tk.Frame):
    def __init__(self, master, setup_app):
        super().__init__(master)
        self.is_playing = False
        self.setup_app = setup_app

        # Khởi tạo giá trị cho slider
        self.current_listbox_value = tk.IntVar(value=1)  # Bắt đầu với giá trị 1
        self.total_listbox_lines = 1  # Số lượng dòng ban đầu

        # Đường dẫn của file .HAT hiện hành
        self.current_hat_file = "default.HAT"

        # Tạo file .HAT mặc định nếu chưa tồn tại
        if not os.path.exists(self.current_hat_file):
            open(self.current_hat_file, "w").close()

        # Tạo frame karaoke với tên file .HAT
        self.karaoke_frame = tk.LabelFrame(master, text=f"Karaoke - ({self.current_hat_file})",
                                           font=("Arial", 16, "bold"), labelanchor='n')
        self.karaoke_frame.grid(row=0, column=2, columnspan=2, padx=10, pady=10)

        # Textbox hiển thị nội dung file .HAT
        self.textbox = scrolledtext.ScrolledText(self.karaoke_frame, width=38, height=15, wrap=tk.WORD)
        self.textbox.grid(row=0, column=0, columnspan=4, padx=5, pady=5)

        # Thêm checkbox "Lưu kịch bản"
        self.save_checkbox_var = tk.BooleanVar()
        self.save_checkbox = tk.Checkbutton(self.karaoke_frame, text="Lưu kịch bản", variable=self.save_checkbox_var)
        self.save_checkbox.grid(row=2, column=1, pady=5, padx=5)

        # Frame chứa listbox và scrollbar
        listbox_frame = tk.Frame(self.karaoke_frame)
        listbox_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=5)

        # Listbox hiển thị converted_text
        self.converted_listbox = tk.Listbox(listbox_frame, width=30, height=10)
        self.converted_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.converted_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.converted_listbox.config(yscrollcommand=scrollbar.set)

        # Thay thế phần tạo các nút bằng hình ảnh từ ImageManager

        # Nút PLAY/PAUSE với hình ảnh "play"
        self.play_button = tk.Button(self.karaoke_frame,text="Play",command=self.toggle_play_pause,
            image=self.setup_app.image_manager.get_image("play"),  # Thay "play" bằng tên key ảnh phù hợp
            compound="top", bd=0)
        self.play_button.grid(row=3, column=2, pady=5, padx=5)

        # Nút SAVE với hình ảnh "save"
        self.save_button = tk.Button(
            self.karaoke_frame,
            text="SAVE",
            command=self.save_hat_file,
            image=self.setup_app.image_manager.get_image("save"),  # Thay "save" bằng tên key ảnh phù hợp
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        self.save_button.grid(row=3, column=1, pady=5, padx=5)

        # Nút NEW với hình ảnh "new"
        self.new_button = tk.Button(
            self.karaoke_frame,
            text="NEW",
            command=self.new_hat_file,
            image=self.setup_app.image_manager.get_image("new"),  # Thay "new" bằng tên key ảnh phù hợp
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        self.new_button.grid(row=3, column=3, pady=5, padx=5)

        # Nút LOAD với hình ảnh "load"
        self.load_button = tk.Button(
            self.karaoke_frame,
            text="LOAD",
            command=self.load_hat_file,
            image=self.setup_app.image_manager.get_image("load"),  # Thay "load" bằng tên key ảnh phù hợp
            compound="top",
            bd=0  # Bỏ viền ngoài
        )
        self.load_button.grid(row=3, column=0, pady=5, padx=5)

        # Đọc nội dung file .HAT nếu có
        self.load_hat_content()

        # Sự kiện thay đổi Textbox
        self.textbox.bind("<<Modified>>", self.on_text_modified)

        # Load dữ liệu từ Mouth.BOT
        self.vowel_dict = self.load_vowel_data()

        # Khởi tạo chỉ số được chọn hiện tại (khởi tạo giá trị là 0)
        self.current_selection_index = 0

        # Liên kết sự kiện <<ListboxSelect>> với hàm on_listbox_select
        self.converted_listbox.bind("<<ListboxSelect>>", self.on_listbox_select)

        # Liên kết sự kiện khi nội dung của listbox thay đổi hoặc khi bạn muốn cập nhật
        master.bind("<FocusIn>", self.ensure_selection)

        self.kb_file = None  # Khởi tạo biến file .KB

    def toggle_play_pause(self):
        """Chuyển đổi trạng thái PLAY/PAUSE và cập nhật Listbox"""
        if self.is_playing:
            self.is_playing = False
            pygame.mixer.music.pause()
            self.play_button.config(text="PLAY")

            # Đóng file KB khi kết thúc PLAY
            if self.kb_file is not None:
                try:
                    self.kb_file.close()
                except IOError as e:
                    messagebox.showerror("Lỗi", f"Không thể đóng file .KB: {e}")
                self.kb_file = None  # Đặt lại biến self.kb_file thành None

        else:
            # Khi chuyển sang PLAY, lấy vị trí hiện hành của Listbox
            self.current_selection_index = self.converted_listbox.curselection()[
                0] if self.converted_listbox.curselection() else 0

            self.is_playing = True
            self.play_button.config(text="PAUSE")
            self.start_playing_mp3()
            self.update_listbox_items()

            # Nếu checkbox "Lưu kịch bản" được chọn
            if self.save_checkbox_var.get():
                self.create_and_open_kb_file()  # Đảm bảo file .KB được mở
                self.record_current_state()  # Ghi dòng đầu tiên ngay khi bắt đầu PLAY

    def create_and_open_kb_file(self):
        """Mở file .KB tương ứng với file .HAT hiện hành"""
        self.kb_file_path = os.path.splitext(self.current_hat_file)[0] + ".KB"
        try:
            self.kb_file = open(self.kb_file_path, "w")  # Mở file .KB ở chế độ ghi để xóa nội dung cũ nếu có
        except IOError as e:
            messagebox.showerror("Lỗi", f"Không thể mở file .KB: {e}")
            self.kb_file = None

    def record_current_state(self):
        """Ghi trạng thái hiện tại của 16 sliders vào file .KB"""
        if self.kb_file is not None:
            # Lấy giá trị 16 sliders từ SetupApp (thông qua setup_app)
            current_values = [str(int(self.setup_app.vars[i].get())) for i in range(1, 17)]
            line = ','.join(current_values) + '\n'

            try:
                self.kb_file.write(line)
                self.kb_file.flush()  # Đảm bảo ghi ngay vào file

            except IOError as e:
                messagebox.showerror("Lỗi", f"Không thể ghi vào file .KB: {e}")

    def on_listbox_select(self, event=None):
        """Xử lý khi người dùng chọn mục trong Listbox"""
        selection = self.converted_listbox.curselection()
        if selection:
            self.current_selection_index = selection[0]
            selected_value = self.converted_listbox.get(self.current_selection_index)

            # Cập nhật sliders dựa trên lựa chọn trong Listbox
            key_to_compare = selected_value.split(':')[0].strip()[:2]  # Lấy 2 ký tự đầu tiên
            if key_to_compare in self.vowel_dict:
                slider_values = self.vowel_dict[key_to_compare]
                for i, value in enumerate(slider_values):
                    self.setup_app.vars[i + 1].set(value)  # Giả sử các sliders tương ứng từ 1 đến 16

            # Cập nhật trạng thái của ứng dụng nếu cần
            if self.setup_app:
                self.setup_app.update_mouth_and_eyes()

            # Nếu checkbox "Lưu kịch bản" được chọn và đang trong chế độ PLAY
            if self.is_playing and self.save_checkbox_var.get():
                self.record_current_state()

    def update_sliders_based_on_selection(self):
        """Cập nhật các sliders dựa trên mục được chọn trong Listbox"""
        selected_value = self.converted_listbox.get(self.current_selection_index)
        # Sử dụng giá trị được chọn để cập nhật sliders
        key_to_compare = selected_value.split(':')[0].strip()[:2]  # Lấy 2 ký tự đầu tiên
        if key_to_compare in self.vowel_dict:
            slider_values = self.vowel_dict[key_to_compare]
            for i, value in enumerate(slider_values):
                if i < len(self.sliders):
                    self.sliders[i].set(value)
            if self.setup_app:
                self.setup_app.update_mouth_and_eyes()

    def ensure_selection(self, event=None):
        """Đảm bảo mục trong Listbox luôn được chọn"""
        if self.converted_listbox.size() > 0:
            if self.current_selection_index >= self.converted_listbox.size():
                self.current_selection_index = self.converted_listbox.size() - 1

            self.converted_listbox.selection_clear(0, tk.END)
            self.converted_listbox.selection_set(self.current_selection_index)
            self.converted_listbox.see(self.current_selection_index)

    def update_listbox_items(self):
        """Cập nhật các mục của Listbox khi đang chơi và quay lại dòng đầu tiên khi kết thúc."""
        if self.is_playing:
            if self.current_selection_index < self.converted_listbox.size() - 1:
                self.current_selection_index += 1
                self.converted_listbox.selection_clear(0, tk.END)
                self.converted_listbox.selection_set(self.current_selection_index)
                self.converted_listbox.see(self.current_selection_index)
                self.on_listbox_select(None)
                self.after(200, self.update_listbox_items)
            else:
                # Đã đến dòng cuối, dừng nhạc và chọn lại dòng đầu tiên
                self.is_playing = False
                pygame.mixer.music.stop()
                self.play_button.config(text="PLAY")

                # Chọn lại dòng đầu tiên
                self.current_selection_index = 0
                self.converted_listbox.selection_clear(0, tk.END)
                self.converted_listbox.selection_set(self.current_selection_index)
                self.converted_listbox.see(self.current_selection_index)
                self.on_listbox_select(None)

    def update_sliders_based_on_selection(self):
        """Cập nhật các sliders dựa trên mục được chọn trong Listbox"""
        selected_value = self.converted_listbox.get(self.current_selection_index)
        # Thực hiện các bước xử lý như trước đây để cập nhật sliders từ giá trị được chọn
        # Gọi hàm cập nhật vẽ lại miệng/eyes nếu cần
        self.control_sliders_based_on_listbox()  # Bạn có thể gọi hàm này nếu cần

    def ensure_selection(self, event=None):
        """Đảm bảo mục trong Listbox luôn được chọn"""
        if self.converted_listbox.size() > 0:
            # Kiểm tra xem chỉ số hiện tại có hợp lệ không
            if self.current_selection_index >= self.converted_listbox.size():
                self.current_selection_index = self.converted_listbox.size() - 1

            # Đảm bảo luôn giữ mục được chọn
            self.converted_listbox.selection_clear(0, tk.END)
            self.converted_listbox.selection_set(self.current_selection_index)
            self.converted_listbox.see(self.current_selection_index)

    def load_hat_content(self):
        """Nạp nội dung từ file .HAT vào Textbox"""
        if os.path.exists(self.current_hat_file):
            with open(self.current_hat_file, "r", encoding='utf-8', errors='ignore') as file:
                content = file.read()
                self.textbox.delete("1.0", tk.END)
                self.textbox.insert(tk.END, content)

    def on_text_modified(self, event=None):
        """Cập nhật nội dung Listbox dựa trên Textbox"""
        self.textbox.edit_modified(False)
        # Cập nhật Listbox và slide khi Textbox thay đổi
        content = self.textbox.get("1.0", tk.END).strip()
        if content:
            self.update_listbox(content)

    def update_listbox(self, converted_text):
        """Cập nhật nội dung Listbox"""
        self.converted_listbox.delete(0, tk.END)
        for item in converted_text.split(','):
            self.converted_listbox.insert(tk.END, item)
        self.converted_listbox.see(tk.END)

    def start_playing_mp3(self):
        """Phát file mp3 từ vị trí hiện hành trong Listbox."""
        mp3_file = os.path.splitext(self.current_hat_file)[0] + ".mp3"

        if os.path.exists(mp3_file):
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()

                pygame.mixer.music.load(mp3_file)

                # Sử dụng vị trí hiện hành của listbox để bắt đầu phát
                start_time = self.current_selection_index / 5  # 5 dòng tương ứng với 1 giây
                pygame.mixer.music.play(start=start_time)

            except pygame.error as e:
                messagebox.showerror("Lỗi", f"Không thể phát tệp MP3: {e}")
        else:
            messagebox.showwarning("Cảnh báo", f"Không tìm thấy file MP3 '{mp3_file}'")

    def convert_text_to_vowel_image(self, text_trans):
        """Chuyển đổi văn bản thành chuỗi hình ảnh nguyên âm cho phát âm"""
        replacements = {
            'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a', 'ă': 'ă', 'ằ': 'ă', 'ắ': 'ă', 'ẳ': 'ă', 'ẵ': 'ă',
            'ặ': 'ă', 'â': 'â', 'ầ': 'â', 'ấ': 'â', 'ẩ': 'â', 'ẫ': 'â', 'ậ': 'â', 'è': 'e', 'é': 'e', 'ẻ': 'e',
            'ẽ': 'e', 'ẹ': 'e', 'ê': 'ê', 'ề': 'ê', 'ế': 'ê', 'ể': 'ê', 'ễ': 'ê', 'ệ': 'ê', 'ì': 'i', 'í': 'i',
            'ỉ': 'i', 'ĩ': 'i', 'ị': 'i', 'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o', 'ô': 'ô', 'ồ': 'ô',
            'ố': 'ô', 'ổ': 'ô', 'ỗ': 'ô', 'ộ': 'ô', 'ơ': 'ơ', 'ờ': 'ơ', 'ớ': 'ơ', 'ở': 'ơ', 'ỡ': 'ơ', 'ợ': 'ơ',
            'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u', 'ư': 'ư', 'ừ': 'ư', 'ứ': 'ư', 'ử': 'ư', 'ữ': 'ư',
            'ự': 'ư', 'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y', 'đ': 'd'
        }

        vowel_to_image = {
            "a": "A0", "ă": "AW", "â": "AA", "e": "E0", "ê": "EE", "i": "IY", "y": "IY", "o": "O0", "ô": "OO",
            "ơ": "OW", "u": "U0", "ư": "UW", "!": "DF"
        }

        # Nguyên âm đôi và nguyên âm ba cần được xử lý đặc biệt
        diphthongs = ["oa", "oe", "uy", "ua", "uê", "iê", "ươ", "ui", "ai", "ao", "âu", "ưu", "ơi"]
        triphthongs = ["oai", "uôi", "iêu", "oay", "uây"]

        # Loại bỏ dấu bằng cách sử dụng replacements
        text_without_diacritics = ''.join(replacements.get(c, c) for c in text_trans.lower())

        converted_lines = []
        word_converted = []

        words = text_trans.split()

        for original_word in words:
            if original_word == "~":
                # Nếu gặp ký tự "~", thêm dòng trước đó vào converted_lines
                if converted_lines:
                    converted_lines.append(converted_lines[-1])
            else:
                word = ''.join(replacements.get(c, c) for c in original_word.lower())
                word_converted = []
                i = 0
                while i < len(word):
                    # Kiểm tra nguyên âm ba trước
                    if i < len(word) - 2 and word[i:i + 3] in triphthongs:
                        triphthong = word[i:i + 3]
                        two_last_vowels = triphthong[1:]
                        word_converted.append(f"{vowel_to_image[two_last_vowels[0]]}: {original_word[:i + 2]}")
                        word_converted.append(f"{vowel_to_image[two_last_vowels[1]]}: {original_word[i + 2:]}")
                        i += 3  # Bỏ qua ba ký tự của nguyên âm ba
                    # Kiểm tra nguyên âm đôi nếu không phải nguyên âm ba
                    elif i < len(word) - 1 and word[i:i + 2] in diphthongs:
                        diphthong = word[i:i + 2]
                        word_converted.append(f"{vowel_to_image[diphthong[0]]}: {original_word[:i + 1]}")
                        word_converted.append(f"{vowel_to_image[diphthong[1]]}: {original_word[i + 1:]}")
                        i += 2  # Bỏ qua hai ký tự của nguyên âm đôi
                    else:
                        if word[i] in vowel_to_image:
                            word_converted.append(f"{vowel_to_image[word[i]]}: {original_word}")
                        i += 1

                # Thêm kết quả chuyển đổi của từng từ vào danh sách
                if word_converted:
                    converted_lines.extend(word_converted)

        # Trả về kết quả cuối cùng đã chuyển đổi thành chuỗi để đưa vào listbox
        return ','.join(converted_lines)

    def on_text_modified(self, event):
        self.textbox.edit_modified(False)
        original_text = self.textbox.get("1.0", tk.END).strip()
        if original_text:
            converted_text = self.convert_text_to_vowel_image(original_text)
            self.update_listbox(converted_text)

    def on_text_modified(self, event):
        """Hàm xử lý khi nội dung của TextBox 1 thay đổi"""
        self.textbox.edit_modified(False)

        # Lấy nội dung mới nhất và chuyển đổi
        original_text = self.textbox.get("1.0", tk.END).strip()
        if original_text:
            converted_text = self.convert_text_to_vowel_image(original_text)
            self.update_listbox(converted_text)

    def load_vowel_data(self):
        """Load dữ liệu từ Mouth.BOT vào từ điển."""
        vowel_dict = {}
        try:
            with open('Mouth.BOT', 'r', encoding='utf-8', errors='ignore') as file:
                for line in file:
                    parts = line.strip().split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        values = list(map(int, parts[1].strip().split(',')))
                        vowel_dict[key] = values
        except FileNotFoundError:
            messagebox.showerror("Lỗi", "Không tìm thấy file Mouth.BOT")
        return vowel_dict

    def save_hat_file(self):
        """Lưu nội dung từ Textbox vào file .HAT hiện hành."""
        try:
            with open(self.current_hat_file, "w") as file:
                content = self.textbox.get("1.0", tk.END)
                file.write(content.strip())
            messagebox.showinfo("Thành công", f"Nội dung đã được lưu vào file {self.current_hat_file}")
        except FileNotFoundError:
            messagebox.showerror("Lỗi", f"Không thể lưu file {self.current_hat_file}")

    def new_hat_file(self):
        new_file = simpledialog.askstring("Tạo file .HAT mới", "Nhập tên file mới (không bao gồm đuôi .HAT):")
        if new_file:
            new_file_with_ext = f"{new_file}.HAT"
            open(new_file_with_ext, "w").close()
            self.current_hat_file = new_file_with_ext
            self.textbox.delete("1.0", tk.END)
            self.converted_listbox.delete(0, tk.END)
            self.karaoke_frame.config(text=f"Karaoke - ({self.current_hat_file})")

    def load_hat_file(self):
        """Hiển thị danh sách các file .HAT và chọn file để nạp nội dung vào Textbox."""
        load_window = tk.Toplevel(self)
        load_window.title("Chọn file .HAT")

        hat_listbox = tk.Listbox(load_window, height=10, width=40)
        hat_listbox.pack(padx=10, pady=10)

        # Thêm các file .HAT hiện có vào Listbox
        for filename in os.listdir("."):
            if filename.endswith(".HAT"):
                hat_listbox.insert(tk.END, filename)

        def select_hat_file():
            selection = hat_listbox.curselection()
            if selection:
                selected_file = hat_listbox.get(selection[0])
                self.current_hat_file = selected_file  # Cập nhật file .HAT hiện hành
                self.load_hat_content()  # Tải nội dung vào Textbox
                self.karaoke_frame.config(text=f"Karaoke - ({self.current_hat_file})")  # Cập nhật tên Frame
                load_window.destroy()

        select_button = tk.Button(load_window, text="Chọn", command=select_hat_file)
        select_button.pack(pady=5)

class SetupApp:

    def __init__(self, root, image_manager):
        self.root = root
        # Đặt vị trí cửa sổ tại (50, 50)
        self.root.geometry("+50+50")

        # Không cho phép phóng to/thu nhỏ
        self.root.resizable(False, False)

        self.image_manager = image_manager
        self.root.title("Rotbot Mouth and Eyes")
        self.image_manager = image_manager
        # Tạo menu chính
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # Thêm menu ROBOT
        self.robot_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="ROBOT", menu=self.robot_menu)

        # Thêm mục Option vào menu ROBOT
        self.robot_menu.add_command(label="Option", command=self.show_options)

        # Thêm menu VIEW
        self.view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="VIEW", menu=self.view_menu)

        # Biến trạng thái cho menu VIEW, sử dụng IntVar để quản lý lựa chọn duy nhất
        self.selected_view = tk.IntVar(value=1)  # Mặc định chọn Mouth & Eye Control

        # Thêm các mục vào menu VIEW sử dụng Radiobutton
        self.view_menu.add_radiobutton(label="Mouth & Eye Control", variable=self.selected_view, value=1,
                                       command=self.toggle_frames)
        self.view_menu.add_radiobutton(label="Karaoke", variable=self.selected_view, value=2,
                                       command=self.toggle_frames)
        self.view_menu.add_radiobutton(label="Scenario", variable=self.selected_view, value=3,
                                       command=self.toggle_frames)
        self.view_menu.add_radiobutton(label="Học tập", variable=self.selected_view, value=4,
                                       command=self.toggle_frames)

        # Khởi tạo Frame Arduino
        self.arduino_frame = tk.LabelFrame(self.root, text="Face & Arduino",  font=("Arial", 16, "bold"), labelanchor='n')
        self.arduino_frame.grid(row=0, column=1, padx=10, pady=10, ipadx=5, ipady=5, sticky="n")

        self.canvas = tk.Canvas(self.arduino_frame, width=385, height=380, bg='peachpuff')
        self.canvas.grid(row=0, column=0, columnspan=2, padx=5, pady=(10, 5))

        # Tạo Combobox tương tự menu VIEW
        self.combobox_var = tk.IntVar(value=1)  # Sử dụng IntVar tương tự menu VIEW
        self.view_combobox = ttk.Combobox(self.arduino_frame, textvariable=self.combobox_var, state="readonly")

        # Đặt các lựa chọn vào Combobox
        self.view_combobox['values'] = ("Mouth & Eye Control", "Karaoke", "Scenario", "Học tập")

        # Đặt lựa chọn mặc định
        self.view_combobox.current(0)  # Index 0 tương ứng với "Mouth & Eye Control"
        self.view_combobox.grid(row=2, column=1, columnspan=2, pady=10)  # Đặt vị trí cho Combobox

        # Gán sự kiện khi thay đổi lựa chọn
        self.view_combobox.bind("<<ComboboxSelected>>", self.on_combobox_change)

        # Thêm Label "Cửa sổ làm việc"
        self.label_working_window = tk.Label(self.arduino_frame, text="Cửa sổ làm việc")
        self.label_working_window.grid(row=2, column=0, pady=10)  # Đặt vị trí cho Label

        self.arduino = ArduinoConnection()

        # Khởi tạo các Frame chính
        self.mouth_frame = tk.LabelFrame(self.root, text="Mouth Controls",  font=("Arial", 16, "bold"), labelanchor='n')
        self.mouth_frame.grid(row=0, column=0, padx=10, pady=10)

        self.eye_frame = tk.LabelFrame(self.root, text="Eye Controls",  font=("Arial", 16, "bold"), labelanchor='n')
        self.eye_frame.grid(row=0, column=2, padx=10, pady=10)

        self.vars = {i: tk.DoubleVar(value=1) for i in range(1, 17)}

        self.mouth_drawer = MouthDrawer(self.canvas, self.vars)
        self.eye_drawer = EyeDrawer(self.canvas, self.vars)

        self.slider_manager = SliderManager(self.root, self.vars, self.update_mouth_and_eyes)
        self.create_sliders_in_frames()
        self.create_buttons()
        self.create_listboxes()

        # Các frame và đối tượng khác
        self.karaoke_frame = KaraokeFrame(self.root, self)

        self.scenario_app = ScenarioApp(self.root, self.slider_manager, self)
        self.scenario_frame = self.scenario_app.scenario_frame
        self.scenario_frame.grid(row=1, column=0, padx=10, pady=10, columnspan=3)

        # Truyền chính đối tượng SetupApp (self) vào lớp SpeechFrame
        self.speech_frame = SpeechFrame(self, self.root)

        # Tải dữ liệu mouth và eye
        self.load_mouth_data()
        self.load_eye_data()

        # Khởi tạo vẽ mouth và eyes
        self.draw_mouth_and_eyes()
        self.slider_manager.reset_sliders()

        # Hiển thị trạng thái mặc định của các Frame
        self.toggle_frames()

        # Cấu hình lưới cho root
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, weight=1)


    def show_options(self):
        """Hàm mở cửa sổ tùy chọn đã tồn tại."""
        if hasattr(self, 'speech_frame'):
            self.speech_frame.show_options()

    def toggle_frames(self):
        """Ẩn tất cả các frame ngoại trừ frame được chọn từ menu VIEW hoặc Combobox"""
        self.mouth_frame.grid_remove()
        self.eye_frame.grid_remove()
        self.karaoke_frame.karaoke_frame.grid_remove()
        self.scenario_frame.grid_remove()
        self.speech_frame.chatbox_frame.grid_remove()

        selected = self.selected_view.get() if self.view_combobox.current() == -1 else self.view_combobox.current() + 1


        if selected == 1:  # Mouth & Eye Control
            self.mouth_frame.grid()
            self.eye_frame.grid()
            root.geometry("1050x550")
        elif selected == 2:  # Karaoke
            self.karaoke_frame.karaoke_frame.grid()
            root.geometry("820x550")
        elif selected == 3:  # Scenario
            self.scenario_frame.grid()
            self.mouth_frame.grid()
            self.eye_frame.grid()
            root.geometry("1050x730")
        elif selected == 4:  # Học tập
            self.speech_frame.chatbox_frame.grid()
            root.geometry("820x550")

    def on_combobox_change(self, event):
        """Hàm xử lý sự kiện khi lựa chọn Combobox thay đổi"""
        self.selected_view.set(self.view_combobox.current() + 1)
        self.toggle_frames()

    def _get_state_data(self, data_type):
        if data_type == 'mouth':
            return self.face_data, self.listbox_mouth, 'Mouth.BOT'
        else:
            return self.eye_data, self.listbox_eye, 'Eye.BOT'

    def add_state(self, data_type):
        """Thêm trạng thái mới."""
        state_name = simpledialog.askstring("Add State", f"Enter name for new {data_type} state:")
        data, listbox, file_name = self._get_state_data(data_type)

        if state_name and state_name not in data:
            if data_type == 'mouth':
                values = [int(self.vars[i].get()) for i in range(1, 9)]
            else:
                values = [int(self.vars[i].get()) for i in range(9, 16)]

            data[state_name] = values
            listbox.insert(tk.END, state_name)
            self._save_state_data(file_name, data)
            messagebox.showinfo("Success", f"State '{state_name}' has been added.")
        else:
            messagebox.showwarning("Warning", f"{data_type.capitalize()} state name is empty or already exists.")

    def rename_state(self, data_type):
        """Đổi tên trạng thái hiện tại."""
        data, listbox, file_name = self._get_state_data(data_type)
        selection = listbox.curselection()
        if selection:
            old_name = listbox.get(selection[0])
            new_name = simpledialog.askstring("Rename State", f"Enter new name for the {data_type} state:")
            if new_name and new_name not in data:
                data[new_name] = data.pop(old_name)
                listbox.delete(selection[0])
                listbox.insert(selection[0], new_name)
                self._save_state_data(file_name, data)
                messagebox.showinfo("Success", f"State '{old_name}' has been renamed to '{new_name}'.")
            else:
                messagebox.showwarning("Warning", f"Invalid or existing {data_type} state name.")

    def save_state(self, data_type):
        """Lưu trạng thái hiện tại."""
        data, listbox, file_name = self._get_state_data(data_type)
        selection = listbox.curselection()

        if selection:
            state_name = listbox.get(selection[0])
            if data_type == 'mouth':
                values = [int(self.vars[i].get()) for i in range(1, 9)]
            else:
                values = [int(self.vars[i].get()) for i in range(9, 16)]

            data[state_name] = values
            self._save_state_data(file_name, data)
            messagebox.showinfo("Success", f"State '{state_name}' has been saved.")
        else:
            messagebox.showwarning("Warning", "No state selected to save.")

    def delete_state(self, data_type):
        """Xóa trạng thái hiện tại."""
        data, listbox, file_name = self._get_state_data(data_type)
        selection = listbox.curselection()

        if selection:
            selected_key = listbox.get(selection[0])
            if messagebox.askyesno("Confirm Delete", f"Do you want to delete {data_type} state: {selected_key}?"):
                data.pop(selected_key)
                listbox.delete(selection[0])
                self._save_state_data(file_name, data)
                messagebox.showinfo("Success", f"State '{selected_key}' has been deleted.")
        else:
            messagebox.showwarning("Warning", f"No {data_type} state selected to delete.")

    def _save_state_data(self, file_name, data):
        with open(file_name, 'w') as file:
            for key, values in data.items():
                values_as_int = [int(value) for value in values]
                file.write(f"{key}: {','.join(map(str, values_as_int))}\n")

    def update_sliders_from_text_trans(self, text_trans):
        trans_parts = text_trans.split(",")
        for part in trans_parts:
            for idx, item in enumerate(self.listbox_mouth.get(0, tk.END)):
                if part == item:
                    self.listbox_mouth.selection_clear(0, tk.END)
                    self.listbox_mouth.selection_set(idx)
                    self.listbox_mouth.see(idx)
                    self.on_mouth_select(None)
                    self.root.update()
                    self.root.after(200)

    def create_sliders_in_frames(self):
        slider_info_mouth = [
            ("Lip_Up", 1), ("Lip_Lo", 2), ("Lip_L_Up", 3), ("Lip_R_Up", 4),
            ("Lip_L_Low", 5), ("Lip_L_Lo", 6), ("Tongue", 8), ("Jaw_L", 7),
            ("Jaw_R", 16)
        ]
        for i, (label_text, slide_num) in enumerate(slider_info_mouth):
            self.slider_manager.create_slider(label_text, slide_num, i, 0, self.mouth_frame)

        slider_info_eye = [
            ("Pupil_X_L", 9), ("Pupil_Y_L", 10), ("Pupil_X_R", 11),
            ("Pupil_Y_R", 12), ("Eyelid_L", 13), ("Eyelid_R", 14), ("Eyebrow", 15)
        ]
        for i, (label_text, slide_num) in enumerate(slider_info_eye):
            self.slider_manager.create_slider(label_text, slide_num, i, 0, self.eye_frame)

    def create_buttons(self):
        # Danh sách các nút trong frame Mouth
        mouth_buttons = [
            ("Add", lambda: self.add_state('mouth'), 9, 0, "add"),
            ("Save", lambda: self.save_state('mouth'), 9, 1, "save"),
            ("Rename", lambda: self.rename_state('mouth'), 10, 0, "rename"),
            ("Delete", lambda: self.delete_state('mouth'), 10, 1, "delete"),
            ("Reset", self.slider_manager.reset_mouth_sliders, 10, 3, "reset")
        ]

        # Tạo các nút với hình ảnh tương ứng từ ImageManager
        for name, command, row, column, image_key in mouth_buttons:
            button = tk.Button(
                self.mouth_frame,
                text=name,
                command=command,
                image=self.image_manager.get_image(image_key),
                compound="top",  # Hiển thị hình ảnh phía trên chữ
                borderwidth=0,  # Loại bỏ viền xung quanh nút
                highlightthickness=0  # Loại bỏ viền nổi bật
            )
            button.grid(row=row, column=column, pady=1, padx=1)

        # Danh sách các nút trong frame Eye
        eye_buttons = [
            ("Add", lambda: self.add_state('eye'), 8, 0, "add"),
            ("Save", lambda: self.save_state('eye'), 8, 1, "save"),
            ("Rename", lambda: self.rename_state('eye'), 9, 0, "rename"),
            ("Delete", lambda: self.delete_state('eye'), 9, 1, "delete"),
            ("Reset", self.slider_manager.reset_eye_sliders, 9, 3, "reset")
        ]

        # Tạo các nút với hình ảnh tương ứng từ ImageManager
        for name, command, row, column, image_key in eye_buttons:
            button = tk.Button(
                self.eye_frame,
                text=name,
                command=command,
                image=self.image_manager.get_image(image_key),
                compound="top",  # Hiển thị hình ảnh phía trên chữ
                borderwidth=0,  # Loại bỏ viền xung quanh nút
                highlightthickness=0  # Loại bỏ viền nổi bật
            )
            button.grid(row=row, column=column, pady=1, padx=1)

        # Nút Connect với hình ảnh "option"
        self.connect_button = tk.Button(
            self.arduino_frame,
            text="Connect",
            command=self.toggle_connection,
            image=self.image_manager.get_image("connect"),
            compound="top",  # Hiển thị hình ảnh phía trên chữ
            borderwidth=0,  # Loại bỏ viền xung quanh nút
            highlightthickness=0  # Loại bỏ viền nổi bật
        )
        self.connect_button.grid(row=1, column=0)

        self.data_label = tk.Label(self.arduino_frame, text="->", bg="lightyellow")
        self.data_label.grid(row=1, column=1)

    def create_listboxes(self):
        self.listbox_mouth = tk.Listbox(self.mouth_frame, width=10, height=23)
        self.listbox_mouth.grid(row=0, column=3, rowspan=10, padx=1, pady=1)
        self.listbox_mouth.bind("<<ListboxSelect>>", self.on_mouth_select)

        self.listbox_eye = tk.Listbox(self.eye_frame, width=10, height=23)
        self.listbox_eye.grid(row=0, column=3, rowspan=9, padx=1, pady=1)
        self.listbox_eye.bind("<<ListboxSelect>>", self.on_eye_select)

    def load_mouth_data(self):
        self.face_data = {}
        try:
            with open('Mouth.BOT', 'r', encoding='utf-8', errors='ignore') as file:
                for line in file:
                    parts = line.strip().split(':')
                    if len(parts) == 2:
                        key = parts[0]
                        values = list(map(float, parts[1].split(',')))
                        if len(values) == 8:
                            self.face_data[key] = values
                            self.listbox_mouth.insert(tk.END, key)

                if self.listbox_mouth.size() > 0:
                    self.listbox_mouth.select_set(0)
                    self.listbox_mouth.event_generate("<<ListboxSelect>>")
        except FileNotFoundError:
            print("File 'Mouth.BOT' not found.")

    def load_eye_data(self):
        self.eye_data = {}
        try:
            with open('Eye.BOT', 'r', encoding='utf-8', errors='ignore') as file:
                for line in file:
                    parts = line.strip().split(':')
                    if len(parts) == 2:
                        key = parts[0]
                        values = list(map(float, parts[1].split(',')))
                        if len(values) == 7:
                            self.eye_data[key] = values
                            self.listbox_eye.insert(tk.END, key)

                if self.listbox_eye.size() > 0:
                    self.listbox_eye.select_set(0)
                    self.listbox_eye.event_generate("<<ListboxSelect>>")
        except FileNotFoundError:
            print("File 'Eye.BOT' not found.")

    def toggle_connection(self):
        self.arduino.toggle_connection(self.connect_button, self.root)

    def on_mouth_select(self, event):
        selection = self.listbox_mouth.curselection()
        if selection:
            selected_key = self.listbox_mouth.get(selection[0])
            if selected_key in self.face_data:
                values = self.face_data[selected_key]
                for i, value in enumerate(values[:8]):
                    self.vars[i + 1].set(value)
                self.update_mouth_and_eyes()
                self.listbox_mouth.see(selection[0])

    def on_eye_select(self, event):
        selection = self.listbox_eye.curselection()
        if selection:
            selected_key = self.listbox_eye.get(selection[0])
            if selected_key in self.eye_data:
                values = self.eye_data[selected_key]
                for i, value in enumerate(values):
                    self.vars[i + 9].set(value)
                self.update_mouth_and_eyes()
                self.listbox_eye.see(selection[0])

    def draw_mouth_and_eyes(self):
        self.canvas.delete("all")
        self.eye_drawer.draw_eyes()
        self.mouth_drawer.draw_mouth()
        self.eye_drawer.draw_nose()
        self.vars[16].set(self.vars[7].get())

    def update_mouth_and_eyes(self, *args):
        self.vars[16].set(self.vars[7].get())
        self.draw_mouth_and_eyes()
        self.send_data_to_arduino()

    def send_data_to_arduino(self):
        data = [self.vars[i].get() for i in range(1, 17)]
        self.arduino.send_data(data)
        formatted_data = [str(int(value)) for value in data]
        data_str = ', '.join(formatted_data)
        self.data_label.config(text=f"-> {data_str}")

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1050x550")

    # Khởi tạo ImageManager
    image_manager = ImageManager()
    # Khởi tạo SetupApp với image_manager
    app = SetupApp(root, image_manager)

    root.mainloop()
    from train import model, env

    state = env.reset()
    done = False
    while not done:
        action = model(np.expand_dims(state, axis=0)).numpy().argmax()
        state, reward, done, _ = env.step(action)
        env.render()    