using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using UnityEngine;

// =========================================================
// AdaptiveDirector : choisit le pays demande et les "faux" drapeaux
// en fonction du niveau du joueur (modele de type Elo, mis a jour en direct).
// Meme logique que ml/policy.py (utilise pour la simulation).
//
// - P(attraper le bon drapeau) = sigmoid(theta_joueur - difficulte_drapeau + ajustement_perso)
// - Pays demande : celui dont la probabilite predite est proche de 70 %,
//   avec un peu de hasard, et un bonus pour les drapeaux rates recemment.
// - Faux drapeaux : quand le joueur reussit bien, ils sont plus souvent choisis
//   parmi les drapeaux qui ressemblent au bon (similarite CLIP).
//
// Place ce script sur le GameObject "GameManager" (ou un GameObject vide).
// Decoche "useAdaptive" pour retrouver le jeu original (tout aleatoire).
// =========================================================
public class AdaptiveDirector : MonoBehaviour
{
    public static AdaptiveDirector Instance;

    [Header("Mode")]
    [Tooltip("Decoche pour jouer au jeu original (choix aleatoires).")]
    public bool useAdaptive = true;

    [Header("Reglages (identiques a ml/policy.py)")]
    [Range(0.3f, 0.95f)] public float targetSuccess = 0.7f;
    public float kPlayer = 0.15f;
    public float kItem = 0.05f;
    public float kPersonal = 0.4f;
    public float temperature = 0.08f;
    public float reviewBonus = 0.15f;
    public int reviewRounds = 8;

    public bool IsActive { get { return useAdaptive && model != null; } }
    public string PolicyName { get { return IsActive ? "adaptive" : "random"; } }

    private FlagModel model;
    private Dictionary<string, FlagModelEntry> entries = new Dictionary<string, FlagModelEntry>();
    private Dictionary<string, float> itemRating = new Dictionary<string, float>();   // b
    private Dictionary<string, float> personal = new Dictionary<string, float>();     // u
    private Dictionary<string, int> review = new Dictionary<string, int>();
    private List<float> recent = new List<float>();
    private float theta = 0f;
    private string playerName = "";

    const string ItemsKey = "FlagFall.items";
    const string PlayerKeyPrefix = "FlagFall.player.";

    void Awake()
    {
        if (Instance == null) Instance = this;
        else { Destroy(this); return; }

        model = FlagModel.Load();
        if (model == null) return;
        entries = model.ByCode();
        targetSuccess = model.target_success > 0 ? model.target_success : targetSuccess;
        LoadItemRatings();
    }

    // ---------- Joueur ----------

    // Appele par le GameLogger quand le joueur a entre son nom.
    public void SetPlayer(string name)
    {
        playerName = name;
        theta = 0f;
        personal.Clear();
        string saved = PlayerPrefs.GetString(PlayerKeyPrefix + name, "");
        if (saved.Length > 0)
        {
            string[] parts = saved.Split('|');
            theta = ParseFloat(parts[0]);
            if (parts.Length > 1) personal = ParsePairs(parts[1]);
        }
    }

    // ---------- Predictions ----------

    public float Predict(string code)
    {
        float b = itemRating.ContainsKey(code) ? itemRating[code] : 0f;
        float u = personal.ContainsKey(code) ? personal[code] : 0f;
        return Sigmoid(theta - b + u);
    }

    // ---------- Choix du pays demande ----------

    public Country PickTarget(List<Country> countries, Country last)
    {
        var candidates = countries.Where(c => last == null || c.Code != last.Code).ToList();
        if (!IsActive || candidates.Count == 0)
            return candidates.Count > 0 ? candidates[Random.Range(0, candidates.Count)] : null;

        var scores = new List<float>();
        foreach (var c in candidates)
        {
            float s = -Mathf.Abs(Predict(c.Code) - targetSuccess);
            if (review.ContainsKey(c.Code)) s += reviewBonus;
            scores.Add(s);
        }
        // Tirage "softmax" : les meilleurs scores sont les plus probables, mais pas certains.
        float max = scores.Max();
        var weights = scores.Select(s => Mathf.Exp((s - max) / temperature)).ToList();
        float r = Random.value * weights.Sum();
        for (int i = 0; i < candidates.Count; i++)
        {
            r -= weights[i];
            if (r <= 0f) return candidates[i];
        }
        return candidates[candidates.Count - 1];
    }

    // ---------- Choix des faux drapeaux ----------

    public float SimilarChance()
    {
        if (recent.Count == 0) return 0.2f;
        float rate = recent.Average();
        return Mathf.Clamp(0.2f + (rate - targetSuccess) * 2f, 0.1f, 0.8f);
    }

    public Country PickDistractor(Country target, List<Country> countries)
    {
        var others = countries.Where(c => c.Code != target.Code).ToList();
        if (others.Count == 0) return target;

        if (IsActive && entries.ContainsKey(target.Code) && Random.value < SimilarChance())
        {
            var lookalikes = others.Where(c => entries[target.Code].similar.Contains(c.Code)).ToList();
            if (lookalikes.Count > 0)
                return lookalikes[Random.Range(0, lookalikes.Count)];
        }
        return others[Random.Range(0, others.Count)];
    }

    // ---------- Mise a jour apres chaque drapeau attrape ----------

    public void Record(Country target, bool correct)
    {
        if (model == null || target == null) return;
        string code = target.Code;
        float y = correct ? 1f : 0f;
        float err = y - Predict(code);

        theta += kPlayer * err;
        itemRating[code] = (itemRating.ContainsKey(code) ? itemRating[code] : 0f) - kItem * err;
        personal[code] = (personal.ContainsKey(code) ? personal[code] : 0f) + kPersonal * err;

        recent.Add(y);
        if (recent.Count > 10) recent.RemoveAt(0);

        foreach (var key in review.Keys.ToList())
        {
            review[key]--;
            if (review[key] <= 0) review.Remove(key);
        }
        if (!correct) review[code] = reviewRounds;

        Save();
    }

    // ---------- Sauvegarde (PlayerPrefs) ----------

    void LoadItemRatings()
    {
        itemRating.Clear();
        foreach (var e in model.countries) itemRating[e.code] = e.difficulty;

        // Si le modele n'a pas change depuis la derniere partie, on reprend les notes mises a jour.
        string saved = PlayerPrefs.GetString(ItemsKey, "");
        string[] parts = saved.Split('|');
        if (parts.Length == 2 && parts[0] == model.created)
            foreach (var kv in ParsePairs(parts[1])) itemRating[kv.Key] = kv.Value;
    }

    void Save()
    {
        PlayerPrefs.SetString(ItemsKey, model.created + "|" + FormatPairs(itemRating));
        if (playerName.Length > 0)
            PlayerPrefs.SetString(PlayerKeyPrefix + playerName,
                theta.ToString(CultureInfo.InvariantCulture) + "|" + FormatPairs(personal));
    }

    void OnApplicationQuit() { PlayerPrefs.Save(); }
    void OnDestroy() { if (Instance == this) PlayerPrefs.Save(); }

    // ---------- Utilitaires ----------

    static float Sigmoid(float x) { return 1f / (1f + Mathf.Exp(-x)); }

    static float ParseFloat(string s)
    {
        float v;
        return float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out v) ? v : 0f;
    }

    static string FormatPairs(Dictionary<string, float> d)
    {
        return string.Join(";", d.Select(kv => kv.Key + "=" + kv.Value.ToString(CultureInfo.InvariantCulture)));
    }

    static Dictionary<string, float> ParsePairs(string s)
    {
        var d = new Dictionary<string, float>();
        foreach (var pair in s.Split(';'))
        {
            var kv = pair.Split('=');
            if (kv.Length == 2) d[kv[0]] = ParseFloat(kv[1]);
        }
        return d;
    }
}
