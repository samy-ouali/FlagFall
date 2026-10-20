using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

// =========================================================
// GameLogger : enregistre chaque partie dans un fichier CSV,
// pour entrainer le modele (ml/train_difficulty.py).
//
// - Au lancement, demande le nom du joueur (le jeu est en pause).
//   Le nom est garde quand on clique sur "Rejouer".
// - Ecrit dans : <Application.persistentDataPath>/FlagFallLogs/<session>.csv
//   (menu Unity : FlagFall > Open logs folder)
//
// Place ce script sur le GameObject "GameManager" (ou un GameObject vide).
// =========================================================
public class GameLogger : MonoBehaviour
{
    public static GameLogger Instance;

    [Tooltip("Demander le nom du joueur au lancement.")]
    public bool askPlayerName = true;

    public static readonly string[] Columns = {
        "session_id", "player", "timestamp", "game_time", "event", "target",
        "caught", "correct", "reaction_time", "fall_speed", "onscreen", "policy"
    };

    public string PlayerName { get; private set; }
    public static string LogFolder { get { return Path.Combine(Application.persistentDataPath, "FlagFallLogs"); } }

    private static string currentPlayer;    // garde le nom quand on relance une partie
    private string sessionId;
    private string filePath;
    private float gameTime;
    private float targetShownAt;
    private bool named;
    private string nameInput = "";
    private readonly List<Dictionary<string, string>> pending = new List<Dictionary<string, string>>();

    void Awake()
    {
        if (Instance == null) Instance = this;
        else { Destroy(this); return; }

        sessionId = DateTime.Now.ToString("yyyyMMdd-HHmmss") + "-" + UnityEngine.Random.Range(1000, 9999);
        Directory.CreateDirectory(LogFolder);
        filePath = Path.Combine(LogFolder, sessionId + ".csv");
        File.WriteAllText(filePath, string.Join(",", Columns) + "\n", Encoding.UTF8);

        nameInput = PlayerPrefs.GetString("FlagFall.lastPlayer", "");
        if (!string.IsNullOrEmpty(currentPlayer)) ConfirmName(currentPlayer);   // bouton "Rejouer" : meme joueur
        else if (askPlayerName) Time.timeScale = 0f;  // pause tant que le nom n'est pas saisi
        else ConfirmName("anonymous");
    }

    void Update()
    {
        gameTime += Time.deltaTime;
    }

    // ---------- Fenetre de saisie du nom (IMGUI, aucune modification de la scene necessaire) ----------

    void OnGUI()
    {
        if (named) return;
        float w = 360, h = 150;
        Rect box = new Rect((Screen.width - w) / 2, (Screen.height - h) / 2, w, h);
        GUI.Box(box, "FlagFall");
        GUI.Label(new Rect(box.x + 20, box.y + 30, w - 40, 20), "Ton prénom ou pseudo :");
        GUI.SetNextControlName("nameField");
        nameInput = GUI.TextField(new Rect(box.x + 20, box.y + 55, w - 40, 25), nameInput, 30);
        GUI.FocusControl("nameField");

        bool enter = Event.current.type == EventType.KeyDown &&
                     (Event.current.keyCode == KeyCode.Return || Event.current.keyCode == KeyCode.KeypadEnter);
        if ((GUI.Button(new Rect(box.x + 20, box.y + 95, w - 40, 30), "Jouer") || enter)
            && nameInput.Trim().Length > 0)
            ConfirmName(nameInput.Trim());
    }

    void ConfirmName(string name)
    {
        // Le nom sert d'identifiant : on retire les caracteres qui casseraient le CSV.
        PlayerName = name.Replace(",", " ").Replace("|", " ").Replace("\n", " ");
        named = true;
        currentPlayer = PlayerName;
        PlayerPrefs.SetString("FlagFall.lastPlayer", PlayerName);
        Time.timeScale = 1f;
        if (AdaptiveDirector.Instance != null) AdaptiveDirector.Instance.SetPlayer(PlayerName);
        foreach (var row in pending) Write(row);
        pending.Clear();
    }

    // ---------- Evenements ----------

    public void LogTargetShown(Country target)
    {
        targetShownAt = gameTime;
        Log("round_start", target, null, null, -1f);
    }

    public void LogCatch(Country target, Country caught, List<Country> onscreen, float fallSpeed)
    {
        Log("catch", target, caught, onscreen, fallSpeed);
    }

    public void LogTargetMissed(Country target, float fallSpeed)
    {
        Log("target_missed", target, null, null, fallSpeed);
    }

    public void LogGameOver(int score)
    {
        var row = BaseRow("game_over");
        row["caught"] = score.ToString(CultureInfo.InvariantCulture);   // score final dans la colonne "caught"
        Enqueue(row);
    }

    void Log(string evt, Country target, Country caught, List<Country> onscreen, float fallSpeed)
    {
        var row = BaseRow(evt);
        row["target"] = target != null ? target.Code : "";
        if (caught != null)
        {
            bool correct = target != null && caught.Code == target.Code;
            row["caught"] = caught.Code;
            row["correct"] = correct ? "1" : "0";
            row["reaction_time"] = F(gameTime - targetShownAt);
        }
        if (fallSpeed >= 0f) row["fall_speed"] = F(fallSpeed);
        if (onscreen != null)
        {
            // Tous les faux drapeaux visibles a ce moment-la (y compris un faux drapeau attrape).
            var codes = new List<string>();
            foreach (var c in onscreen)
                if (c != null && target != null && c.Code != target.Code) codes.Add(c.Code);
            row["onscreen"] = string.Join("|", codes);
        }
        Enqueue(row);
    }

    Dictionary<string, string> BaseRow(string evt)
    {
        var row = new Dictionary<string, string>();
        foreach (var col in Columns) row[col] = "";
        row["session_id"] = sessionId;
        row["timestamp"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture);
        row["game_time"] = F(gameTime);
        row["event"] = evt;
        row["policy"] = AdaptiveDirector.Instance != null ? AdaptiveDirector.Instance.PolicyName : "random";
        return row;
    }

    void Enqueue(Dictionary<string, string> row)
    {
        if (named) Write(row);
        else pending.Add(row);      // ecrit des que le joueur a donne son nom
    }

    void Write(Dictionary<string, string> row)
    {
        row["player"] = PlayerName;
        var values = new List<string>();
        foreach (var col in Columns) values.Add(row[col]);
        File.AppendAllText(filePath, string.Join(",", values) + "\n", Encoding.UTF8);
    }

    static string F(float v) { return v.ToString("0.00", CultureInfo.InvariantCulture); }
}
