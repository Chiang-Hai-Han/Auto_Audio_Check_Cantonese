聽這段粵語音頻，完成以下任務：

1. 逐字轉寫你聽到的內容
2. 與預期台詞比對：{EXPECTED_TEXT}
3. 檢查粵語發音和聲調，有問題的字給出正確粵拼
4. 檢查語調節奏

只輸出以下JSON，用實際內容替換每個欄位：
{
  "transcription": "你聽到的逐字轉寫",
  "content_ok": "是或否",
  "content_detail": "如與預期台詞不同，列出差異，否則填無",
  "pronunciation_ok": "是或否",
  "pronunciation_detail": "發音或聲調錯誤，用「字（正確粵拼）」格式逐字列出，如「米（mai5）」「爺（je4）」，否則填無",
  "intonation_ok": "是或否",
  "intonation_detail": "語調節奏問題，否則填無",
  "verdict": "通過或需修改",
  "summary": "審核總結"
}