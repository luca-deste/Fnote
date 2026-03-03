; fnote - Fast Note Taker (Version 6.0 - International Ultimate Master)
; Features: English UI, Background Coloring, Exact Tag Match, Smart Cross-Filtering, Auto-Rotation
#Requires AutoHotkey v2.0
#SingleInstance Force

global INI_FILE := A_ScriptDir "\fnote.ini"
global LOG_DIR := ""
global CurrentLogFile := ""
global MaxFiles := 100
global TagShortcuts := Map()
global TagColors := Map()
global NotificationsEnabled := false

; --- INITIALIZATION ---
ReadConfig()
CurrentLogFile := GetTodayFile()
CheckRotation() ; Automatic log cleaning based on max_files

; --- CLI ARGUMENTS HANDLING ---
if (A_Args.Length = 0) {
    ShowGUI()
} else if (A_Args.Length = 1 && A_Args[1] = "/view") {
    ShowGUI()
} else if (A_Args.Length = 1 && A_Args[1] = "/today") {
    ShowGUI("", FormatTime(A_Now, "yyyy-MM-dd"))
} else if (A_Args.Length = 2 && A_Args[1] = "/tag") {
    ShowGUI("", "", A_Args[2])
} else if (A_Args.Length >= 2 && A_Args[1] = "/find") {
    filterText := ""
    Loop A_Args.Length - 1 {
        filterText .= A_Args[A_Index + 1] " "
    }
    ShowGUI(Trim(filterText))
} else if (A_Args.Length = 1 && A_Args[1] = "/undo") {
    UndoLastNote()
    ExitApp()
} else {
    ProcessCLI()
}

; --- CONFIGURATION ---

ReadConfig() {
    global INI_FILE, LOG_DIR, MaxFiles, TagShortcuts, TagColors, NotificationsEnabled
    
    ; General Settings
    logDirSetting := IniRead(INI_FILE, "settings", "log_dir", "logs")
    MaxFiles := Number(IniRead(INI_FILE, "settings", "max_files", "100"))
    notifSetting := IniRead(INI_FILE, "settings", "notifications", "0")
    NotificationsEnabled := (notifSetting = "1")
    
    LOG_DIR := (InStr(logDirSetting, ":")) ? logDirSetting : A_ScriptDir "\" . logDirSetting
    
    ; Load Tag Shortcuts
    TagShortcuts := Map()
    try {
        section := IniRead(INI_FILE, "tags")
        Loop Parse, section, "`n", "`r" {
            if (InStr(A_LoopField, "=")) {
                parts := StrSplit(A_LoopField, "=", , 2)
                TagShortcuts[Trim(parts[1])] := Trim(parts[2])
            }
        }
    }

    ; Load Colors from INI (BGR Format)
    TagColors := Map()
    try {
        cSection := IniRead(INI_FILE, "colors")
        Loop Parse, cSection, "`n", "`r" {
            if (InStr(A_LoopField, "=")) {
                parts := StrSplit(A_LoopField, "=", , 2)
                TagColors[Trim(parts[1])] := Number(Trim(parts[2]))
            }
        }
    }

    if (!DirExist(LOG_DIR)) {
        DirCreate(LOG_DIR)
    }
}

CheckRotation() {
    global LOG_DIR, MaxFiles
    if (MaxFiles <= 0) {
        return
    }
    files := []
    Loop Files, LOG_DIR "\fnote_*.txt" {
        files.Push(A_LoopFileName)
    }
    
    if (files.Length > MaxFiles) {
        ; Alphabetical sort (yyyy-mm-dd)
        Loop files.Length {
            i := A_Index
            Loop files.Length - i {
                j := A_Index
                if (StrCompare(files[j], files[j+1]) > 0) {
                    temp := files[j]
                    files[j] := files[j+1]
                    files[j+1] := temp
                }
            }
        }
        numToDelete := files.Length - MaxFiles
        Loop numToDelete {
            FileDelete(LOG_DIR "\" files[A_Index])
        }
    }
}

; --- GUI ---

ShowGUI(initialFilter := "", initialDate := "All", initialTag := "All") {
    MyGui := Gui("+Resize", "fnote Viewer")
    MyGui.SetFont("s10", "Segoe UI")
    
    BtnAdd := MyGui.AddButton("xm w80", "&Add")
    BtnEdit := MyGui.AddButton("x+10 w80", "&Edit")
    BtnDel := MyGui.AddButton("x+10 w80", "&Delete")
    BtnReset := MyGui.AddButton("x+10 w80", "&Reset")
    
    MyGui.AddText("xm y+15", "&Date:")
    DropDate := MyGui.AddDropDownList("x+5 w120 vSelectedDate", ["All"])
    MyGui.AddText("x+15", "&Tag:")
    DropTags := MyGui.AddDropDownList("x+5 w150 vSelectedTag", ["All"])
    MyGui.AddText("x+15", "&Search:")
    EditFilter := MyGui.AddEdit("x+5 w200 vFilter", initialFilter)
    
    LV := MyGui.AddListView("xm y+10 r25 w850", ["Date", "Tags", "Note"])
    LV.ModifyCol(1, 120), LV.ModifyCol(2, 130), LV.ModifyCol(3, 570)
    TxtCount := MyGui.AddText("xm y+5 w150 vCount", "Notes Found: 0")
    
    ; Event Handlers
    BtnAdd.OnEvent("Click", (*) => AddNoteGUI(MyGui, LV, TxtCount, EditFilter, DropTags, DropDate))
    BtnEdit.OnEvent("Click", (*) => EditNoteGUI(LV, TxtCount, EditFilter, DropTags, DropDate))
    BtnDel.OnEvent("Click", (*) => DeleteNote(LV, TxtCount, EditFilter, DropTags, DropDate))
    BtnReset.OnEvent("Click", (*) => ResetFilters(LV, EditFilter, DropTags, DropDate, TxtCount))
    
    EditFilter.OnEvent("Change", (*) => RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount))
    
    ; Smart Cross-Filtering: Tags update based on Date, Dates update based on Tag
    DropTags.OnEvent("Change", (*) => OnTagChange(LV, EditFilter, DropTags, DropDate, TxtCount))
    DropDate.OnEvent("Change", (*) => OnDateChange(LV, EditFilter, DropTags, DropDate, TxtCount))
    
    LV.OnEvent("DoubleClick", (*) => EditNoteGUI(LV, TxtCount, EditFilter, DropTags, DropDate))
    LV.OnEvent("ContextMenu", (LV, Item, IsRightClick, X, Y) => ShowContextMenu(LV, Item, X, Y, MyGui, TxtCount, EditFilter, DropTags, DropDate))
    
    ; Background coloring event
    LV.OnNotify(-12, LV_CustomDraw)

    LoadDates(DropDate)
    LoadTags(DropTags)
    
    if (initialDate != "All") {
        RestoreSelection(DropDate, initialDate)
    }
    if (initialTag != "All") {
        RestoreSelection(DropTags, initialTag)
    }
    
    RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount)
    MyGui.Show("w870 h600")
}

; Logic to prevent auto-resetting to "All"
OnTagChange(LV, EditFilter, DropTags, DropDate, TxtCount) {
    RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount)
    LoadDates(DropDate, DropTags.Text)
}

OnDateChange(LV, EditFilter, DropTags, DropDate, TxtCount) {
    RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount)
    LoadTags(DropTags, DropDate.Text)
}

; Function to color row background
LV_CustomDraw(LV, lParam) {
    static NM_CUSTOMDRAW := -12
    static CDDS_PREPAINT := 0x1, CDDS_ITEMPREPAINT := 0x10001
    static CDRF_NOTIFYITEMDRAW := 0x20, CDRF_NEWFONT := 0x2

    offStage := (A_PtrSize == 8) ? 24 : 12
    offItem  := (A_PtrSize == 8) ? 56 : 36 
    offBkColor := (A_PtrSize == 8) ? 88 : 52 ; Offset for Background color (clrTextBk)

    drawStage := NumGet(lParam, offStage, "UInt")
    
    if (drawStage == CDDS_PREPAINT) {
        return CDRF_NOTIFYITEMDRAW
    }
    
    if (drawStage == CDDS_ITEMPREPAINT) {
        rowIdx := NumGet(lParam, offItem, "UPtr") + 1
        try {
            tagsStr := LV.GetText(rowIdx, 2)
            tagsArr := StrSplit(tagsStr, ",")
            
            for tagName, colorValue in TagColors {
                found := false
                for t in tagsArr {
                    if (Trim(t) == tagName) {
                        found := true
                        break
                    }
                }
                
                if (found) {
                    NumPut("UInt", colorValue, lParam, offBkColor)
                    break
                }
            }
        }
        return CDRF_NEWFONT
    }
    return 0
}

; --- DATA MANAGEMENT ---

RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount) {
    LV.Delete()
    fText := EditFilter.Value
    fTag := (DropTags.Value > 1 ? DropTags.Text : "")
    fDate := (DropDate.Value > 1 ? DropDate.Text : "")
    count := 0
    
    Loop Files, LOG_DIR "\fnote_*.txt" {
        if (fDate != "" && !InStr(A_LoopFileName, fDate)) {
            continue
        }
        Loop Read, A_LoopFileFullPath, "UTF-8" {
            if (A_LoopReadLine == "") {
                continue
            }
            parts := StrSplit(A_LoopReadLine, "|", , 3)
            if (parts.Length < 3) {
                continue
            }
            
            if (fText != "" && !InStr(A_LoopReadLine, fText)) {
                continue
            }
            
            ; Exact Tag Match logic
            if (fTag != "") {
                match := false
                tagsInNote := StrSplit(parts[2], ",")
                for tagPart in tagsInNote {
                    if (Trim(tagPart) == fTag) {
                        match := true
                        break
                    }
                }
                if (!match) {
                    continue
                }
            }
            
            LV.Insert(1, "", parts[1], parts[2], parts[3])
            count++
        }
    }
    TxtCount.Value := "Notes Found: " count
}

LoadTags(DropCtrl, selectedDate := "All") {
    currentTag := DropCtrl.Text
    uniqueTags := Map()
    for k, v in TagShortcuts {
        uniqueTags[v] := 1
    }
    
    Loop Files, LOG_DIR "\fnote_*.txt" {
        if (selectedDate != "All" && !InStr(A_LoopFileName, selectedDate)) {
            continue
        }
        try {
            Loop Read, A_LoopFileFullPath, "UTF-8" {
                parts := StrSplit(A_LoopReadLine, "|", , 3)
                if (parts.Length >= 2) {
                    Loop Parse, parts[2], "," {
                        t := Trim(A_LoopField)
                        if (t != "" && t != "All" && t != "Tutti") {
                            uniqueTags[t] := 1
                        }
                    }
                }
            }
        }
    }
    
    sorted := []
    for tag, _ in uniqueTags {
        sorted.Push(tag)
    }
    
    Loop sorted.Length {
        i := A_Index
        Loop sorted.Length - i {
            j := A_Index
            if (StrCompare(sorted[j], sorted[j+1]) > 0) {
                temp := sorted[j], sorted[j] := sorted[j+1], sorted[j+1] := temp
            }
        }
    }
    
    final := ["All"]
    for tag in sorted {
        final.Push(tag)
    }
    DropCtrl.Delete()
    DropCtrl.Add(final)
    RestoreSelection(DropCtrl, currentTag)
}

LoadDates(DropCtrl, selectedTag := "All") {
    currentDate := DropCtrl.Text
    uniqueDates := Map()
    
    Loop Files, LOG_DIR "\fnote_*.txt" {
        if (!RegExMatch(A_LoopFileName, "\d{4}-\d{2}-\d{2}", &m)) {
            continue
        }
        thisDate := m[0]
        
        if (selectedTag = "All") {
            uniqueDates[thisDate] := 1
            continue
        }
        
        ; If tag is selected, check if file contains that exact tag
        Loop Read, A_LoopFileFullPath, "UTF-8" {
            parts := StrSplit(A_LoopReadLine, "|", , 3)
            if (parts.Length < 2) {
                continue
            }
            found := false
            tagsInNote := StrSplit(parts[2], ",")
            for t in tagsInNote {
                if (Trim(t) == selectedTag) {
                    found := true
                    break
                }
            }
            if (found) {
                uniqueDates[thisDate] := 1
                break
            }
        }
    }
    
    dateList := ["All"]
    for d, _ in uniqueDates {
        dateList.Push(d)
    }
    DropCtrl.Delete()
    DropCtrl.Add(dateList)
    RestoreSelection(DropCtrl, currentDate)
}

RestoreSelection(Ctrl, Value) {
    items := ControlGetItems(Ctrl.Hwnd)
    for i, item in items {
        if (item = Value) {
            Ctrl.Choose(i)
            return true
        }
    }
    Ctrl.Choose(1)
    return false
}

ResetFilters(LV, EditFilter, DropTags, DropDate, TxtCount) {
    EditFilter.Value := ""
    LoadDates(DropDate, "All")
    LoadTags(DropTags, "All")
    DropDate.Choose(1)
    DropTags.Choose(1)
    RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount)
}

; --- ACTIONS (CRUD) ---

AddNoteGUI(GuiObj, LV, TxtCount, EditFilter, DropTags, DropDate) {
    Dialog := Gui("+Owner" GuiObj.Hwnd " +AlwaysOnTop", "Add New Note")
    Dialog.SetFont("s10", "Segoe UI")
    Dialog.AddText(, "Note content:")
    en := Dialog.AddEdit("w400 h80 vNoteField")
    Dialog.AddText(, "Tags (comma separated):")
    et := Dialog.AddEdit("w400 vTagField")
    BtnOK := Dialog.AddButton("w80 +Default", "OK")
    state := {ok: false}
    BtnOK.OnEvent("Click", (*) => (state.ok := true, Dialog.Hide()))
    Dialog.Show()
    WinWaitClose(Dialog)
    
    if (state.ok && en.Value != "") {
        cT := DropTags.Text
        cD := DropDate.Text
        fTags := []
        Loop Parse, et.Value, "," {
            t := Trim(A_LoopField)
            if (t != "") {
                r := ResolveTag(t)
                if (!HasValue(fTags, r)) {
                    fTags.Push(r)
                }
            }
        }
        for at in CheckAutoTag(en.Value) {
            if (!HasValue(fTags, at)) {
                fTags.Push(at)
            }
        }
        if (fTags.Length == 0) {
            fTags.Push("General")
        }
        
        FileAppend(FormatTime(, "yyyy-MM-dd HH:mm") "|" JoinArray(fTags, ",") "|" en.Value "`n", GetTodayFile(), "UTF-8")
        ShowNotification("fnote", "Note Saved", 800)
        
        LoadDates(DropDate, cT)
        LoadTags(DropTags, cD)
        RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount)
    }
    Dialog.Destroy()
}

EditNoteGUI(LV, TxtCount, EditFilter, DropTags, DropDate) {
    r := LV.GetNext()
    if (r == 0) {
        return
    }
    oD := LV.GetText(r, 1), oT := LV.GetText(r, 2), oN := LV.GetText(r, 3)
    Dialog := Gui("+Owner" LV.Gui.Hwnd " +AlwaysOnTop", "Edit Note")
    Dialog.AddText(, "Note content:"), en := Dialog.AddEdit("w400 h80", oN)
    Dialog.AddText(, "Tags:"), et := Dialog.AddEdit("w400", oT)
    BtnOK := Dialog.AddButton("w80 +Default", "OK")
    state := {ok: false}
    BtnOK.OnEvent("Click", (*) => (state.ok := true, Dialog.Hide()))
    Dialog.Show(), WinWaitClose(Dialog)
    
    if (state.ok) {
        cD := DropDate.Text
        path := LOG_DIR "\fnote_" SubStr(oD, 1, 10) ".txt"
        if (FileExist(path)) {
            c := FileRead(path, "UTF-8")
            FileDelete(path)
            FileAppend(StrReplace(c, oD "|" oT "|" oN, oD "|" et.Value "|" en.Value), path, "UTF-8")
            ShowNotification("fnote", "Note Updated", 800)
            LoadTags(DropTags, cD)
            RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount)
        }
    }
    Dialog.Destroy()
}

DeleteNote(LV, TxtCount, EditFilter, DropTags, DropDate) {
    r := LV.GetNext()
    if (r == 0) {
        return
    }
    if (MsgBox("Are you sure you want to delete this note?", "fnote", "YesNo Icon?") == "No") {
        return
    }
    cT := DropTags.Text, cD := DropDate.Text
    oD := LV.GetText(r, 1), oT := LV.GetText(r, 2), oN := LV.GetText(r, 3)
    path := LOG_DIR "\fnote_" SubStr(oD, 1, 10) ".txt"
    
    c := FileRead(path, "UTF-8"), newC := ""
    Loop Parse, c, "`n", "`r" {
        if (A_LoopField != "" && A_LoopField != oD "|" oT "|" oN) {
            newC .= A_LoopField "`n"
        }
    }
    FileDelete(path)
    if (newC != "") {
        FileAppend(newC, path, "UTF-8")
    }
    ShowNotification("fnote", "Note Deleted", 800)
    LoadTags(DropTags, cD), LoadDates(DropDate, cT)
    RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount)
}

; --- CORE UTILITIES ---

ProcessCLI() {
    tags := [], textParts := [], inText := false
    for arg in A_Args {
        if (!inText && SubStr(arg, 1, 1) = "/") {
            tName := SubStr(arg, 2), (tName != "" && tName != "view" ? tags.Push(tName) : 0)
        } else {
            inText := true, textParts.Push(arg)
        }
    }
    txt := Trim(JoinArray(textParts, " ")), (txt == "" ? (MsgBox("Empty text error"), ExitApp()) : 0)
    resTags := []
    for tag in tags {
        r := ResolveTag(tag), (!HasValue(resTags, r) ? resTags.Push(r) : 0)
    }
    for at in CheckAutoTag(txt) {
        (!HasValue(resTags, at) ? resTags.Push(at) : 0)
    }
    (resTags.Length == 0 ? resTags.Push("General") : 0)
    
    FileAppend(FormatTime(, "yyyy-MM-dd HH:mm") "|" JoinArray(resTags, ",") "|" txt "`n", GetTodayFile(), "UTF-8")
    ShowNotification("fnote", "Saved: " JoinArray(resTags, ","), 800)
    ExitApp()
}

CheckAutoTag(text) {
    result := []
    try {
        section := IniRead(INI_FILE, "autotags")
        Loop Parse, section, "`n", "`r" {
            if (InStr(A_LoopField, "=")) {
                p := StrSplit(A_LoopField, "=", , 2)
                if (RegExMatch(text, "i)" p[1])) {
                    r := ResolveTag(p[2])
                    if (!HasValue(result, r)) {
                        result.Push(r)
                    }
                }
            }
        }
    }
    return result
}

ResolveTag(shortcut) => TagShortcuts.Has(shortcut) ? TagShortcuts[shortcut] : shortcut
GetTodayFile() => LOG_DIR "\fnote_" FormatTime(A_Now, "yyyy-MM-dd") ".txt"
ShowNotification(title, text, duration) {
    if (NotificationsEnabled) {
        TrayTip(title, text, duration)
    }
}
HasValue(arr, val) {
    for item in arr {
        if (item = val) {
            return true
        }
    }
    return false
}
JoinArray(arr, sep) {
    res := ""
    for i, v in arr {
        res .= (i=1 ? "" : sep) v
    }
    return res
}

ShowContextMenu(LV, Item, X, Y, GuiObj, TxtCount, EditFilter, DropTags, DropDate) {
    CMenu := Menu()
    if (Item > 0) {
        LV.Modify(Item, "Select Focus")
        CMenu.Add("&Edit", (*) => EditNoteGUI(LV, TxtCount, EditFilter, DropTags, DropDate))
        CMenu.Add("&Duplicate", (*) => DuplicateNote(LV, TxtCount, EditFilter, DropTags, DropDate))
        CMenu.Add("&Copy Content", (*) => CopyToClipboard(LV))
        CMenu.Add()
        CMenu.Add("&Delete", (*) => DeleteNote(LV, TxtCount, EditFilter, DropTags, DropDate))
    } else {
        CMenu.Add("&Add New Note", (*) => AddNoteGUI(GuiObj, LV, TxtCount, EditFilter, DropTags, DropDate))
    }
    CMenu.Show(X, Y)
}

DuplicateNote(LV, TxtCount, EditFilter, DropTags, DropDate) {
    r := LV.GetNext()
    if (r == 0) {
        return
    }
    cT := DropTags.Text, cD := DropDate.Text
    FileAppend(FormatTime(, "yyyy-MM-dd HH:mm") "|" LV.GetText(r, 2) "|" LV.GetText(r, 3) "`n", GetTodayFile(), "UTF-8")
    ShowNotification("fnote", "Duplicated", 800)
    LoadDates(DropDate, cT), LoadTags(DropTags, cD), RefreshList(LV, EditFilter, DropTags, DropDate, TxtCount)
}

UndoLastNote() {
    f := GetTodayFile()
    if (!FileExist(f)) {
        return
    }
    l := StrSplit(Trim(FileRead(f, "UTF-8"), "`n"), "`n")
    if (l.Length > 0) {
        l.Pop()
        FileDelete(f)
        if (l.Length > 0) {
            FileAppend(JoinArray(l, "`n") "`n", f, "UTF-8")
        }
        ShowNotification("fnote", "Last note removed", 800)
    }
}

CopyToClipboard(LV) {
    r := LV.GetNext()
    if (r > 0) {
        A_Clipboard := LV.GetText(r, 3)
        ShowNotification("fnote", "Copied!", 500)
    }
}