from flask import Flask, render_template, request, flash, redirect, url_for, session
import psycopg2
from psycopg2 import sql
import os
import re
import hashlib
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')

# Admin kullanıcı bilgileri - gerçek uygulamada veritabanında şifreli olarak saklanmalı
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'esporadmin2025'

# Admin girişi gerekli olan sayfalar için decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Bu sayfaya erişmek için admin girişi yapmalısınız!', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Kullanıcı girişi gerekli olan sayfalar için decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Bu sayfaya erişmek için giriş yapmalısınız!', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# PostgreSQL bağlantı ayarları
def get_db_connection():
    conn = psycopg2.connect(
        dbname="espor_turnuva_sistemi",
        user="postgres",
        password="admin",
        host="localhost",
        port="5432"
    )
    return conn

# Ana Sayfa
@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Trigger_Logs ORDER BY created_at DESC LIMIT 5")
    trigger_logs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', trigger_logs=trigger_logs)

# Turnuvaları Listeleme
@app.route('/tournaments', methods=['GET', 'POST'])
def tournaments():
    conn = get_db_connection()
    cur = conn.cursor()
    
    game_type = request.form.get('game_type', '')
    status = request.form.get('status', '')
    min_prize = request.form.get('min_prize', '')
    
    query = """
        SELECT 
            tournament_id, 
            game_type, 
            tournament_date, 
            prize_pool, 
            COALESCE(tournament_name, 'Turnuva #' || tournament_id || ' - ' || game_type) AS tournament_name,
            CASE 
                WHEN tournament_date < CURRENT_DATE THEN 'Tamamlandı'
                WHEN tournament_date = CURRENT_DATE THEN 'Bugün'
                ELSE 'Yaklaşan'
            END as status_display
        FROM Tournaments
    """
    conditions = []
    params = []
    
    # Only show future tournaments
    conditions.append("tournament_date >= CURRENT_DATE")
    
    if game_type:
        conditions.append("game_type = %s")
        params.append(game_type)
    
    if min_prize and min_prize.strip():
        try:
            min_prize_value = float(min_prize)
            conditions.append("prize_pool >= %s")
            params.append(min_prize_value)
        except ValueError:
            flash('Geçersiz minimum ödül değeri', 'danger')
    
    if conditions:
        query = query + " WHERE " + " AND ".join(conditions)
    
    # Add order by date
    query += " ORDER BY tournament_date ASC"
    
    cur.execute(query, tuple(params))
    
    tournaments = cur.fetchall()
    
    cur.execute("""
        SELECT u.username, t.game_type, t.tournament_date, tr.rank, tr.prize_won
        FROM Tournament_Results tr
        JOIN Teams tm ON tr.team_id = tm.team_id
        JOIN Users u ON tm.leader_id = u.user_id
        JOIN Tournaments t ON tr.tournament_id = t.tournament_id
        ORDER BY tr.result_id DESC
        LIMIT 10
    """)
    
    history = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('tournaments.html', tournaments=tournaments, history=history)

# Turnuva Detay Sayfası
@app.route('/tournament/<int:tournament_id>')
def tournament_detail(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Önce tournament_name sütunu var mı kontrol edelim
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'tournaments' AND column_name = 'tournament_name'
    """)
    
    has_tournament_name = cur.fetchone() is not None
    
    if has_tournament_name:
        cur.execute("""SELECT tournament_id, game_type, tournament_date, prize_pool, tournament_name 
                      FROM Tournaments WHERE tournament_id = %s""", (tournament_id,))
        tournament_data = cur.fetchone()
    else:
        cur.execute("SELECT * FROM Tournaments WHERE tournament_id = %s", (tournament_id,))
        tournament_data = cur.fetchone()
    
    if not tournament_data:
        flash('Turnuva bulunamadı!', 'danger')
        return redirect(url_for('tournaments'))
    
    # Convert Decimal prize_pool to float to avoid type errors in calculations
    prize_pool = float(tournament_data[3]) if tournament_data[3] is not None else 0.0
    
    # turnuva_name sütunu varsa ve değeri doluysa onu kullan, yoksa otomatik oluştur
    tournament_name = tournament_data[4] if has_tournament_name and tournament_data[4] else f'Turnuva #{tournament_data[0]} - {tournament_data[1]}'
    
    tournament = {
        'tournament_id': tournament_data[0],
        'name': tournament_name,  
        'game_type': tournament_data[1],  
        'start_date': tournament_data[2].strftime('%d.%m.%Y'),  
        'status': 'Aktif',  
        'prize_pool': prize_pool,  
        'description': 'Bu turnuva ' + tournament_data[1] + ' oyununda en iyi takımları bir araya getiriyor. Profesyonel bir ortamda rekabet etme ve büyük ödüller kazanma fırsatı yakala!'
    }
    
    # Katılımcı takımları getir
    cur.execute("""
        SELECT t.team_id, t.team_name, 1 as member_count
        FROM Teams t
        WHERE t.tournament_id = %s
    """, (tournament_id,))
    participating_teams = []
    for team in cur.fetchall():
        participating_teams.append({
            'team_id': team[0],
            'team_name': team[1],
            'member_count': team[2]
        })
    
    user_teams = []
    if 'user_id' in session:
        cur.execute("""
            SELECT t.team_id, t.team_name
            FROM Teams t
            WHERE t.leader_id = %s
        """, (session['user_id'],))
        for team in cur.fetchall():
            user_teams.append({
                'team_id': team[0],
                'team_name': team[1]
            })
    
    cur.close()
    conn.close()
    
    return render_template('tournament_detail.html', 
                           tournament=tournament, 
                           participating_teams=participating_teams,
                           user_teams=user_teams)

# Turnuvaya Katıl
@app.route('/tournament/<int:tournament_id>/join', methods=['POST'])
@login_required
def join_tournament(tournament_id):
    if request.method == 'POST':
        team_id = request.form.get('team_id')
        
        if not team_id:
            flash('Lütfen bir takım seçin!', 'danger')
            return redirect(url_for('tournament_detail', tournament_id=tournament_id))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Turnuvanın tarihini kontrol et - geçmiş turnuvalara katılımı engelle
        from datetime import datetime
        cur.execute("""
            SELECT tournament_date FROM Tournaments 
            WHERE tournament_id = %s
        """, (tournament_id,))
        
        tournament_data = cur.fetchone()
        if not tournament_data:
            flash('Turnuva bulunamadı!', 'danger')
            cur.close()
            conn.close()
            return redirect(url_for('tournaments'))
            
        tournament_date = tournament_data[0]
        current_date = datetime.now().date()
        
        if tournament_date < current_date:
            flash('Bu turnuvanın tarihi geçmiş, katılım yapamazsınız!', 'danger')
            cur.close()
            conn.close()
            return redirect(url_for('tournament_detail', tournament_id=tournament_id))
        
        # Kullanıcının bu takımın lideri olup olmadığını kontrol et
        cur.execute("""
            SELECT * FROM Teams 
            WHERE team_id = %s AND leader_id = %s
        """, (team_id, session['user_id']))
        
        if not cur.fetchone():
            flash('Bu takımın lideri değilsiniz!', 'danger')
            return redirect(url_for('tournament_detail', tournament_id=tournament_id))
        
        # Takımın zaten bu turnuvaya kayıtlı olup olmadığını kontrol et
        cur.execute("""
            SELECT tournament_id FROM Teams 
            WHERE team_id = %s
        """, (team_id,))
        
        team_tournament = cur.fetchone()
        if team_tournament and team_tournament[0] is not None:
            if int(team_tournament[0]) == int(tournament_id):
                flash('Bu takım zaten bu turnuvaya kayıtlı!', 'warning')
                return redirect(url_for('tournament_detail', tournament_id=tournament_id))
            else:
                flash('Bu takım başka bir turnuvaya kayıtlı! Önce o turnuvadan çekilmelisiniz.', 'warning')
                return redirect(url_for('profile'))
        
        try:
            # Takımı turnuvaya kayıt et
            cur.execute("UPDATE Teams SET tournament_id = %s WHERE team_id = %s", (tournament_id, team_id))
            conn.commit()
            flash('Takımınız turnuvaya başarıyla kayıt oldu!', 'success')
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Hata: {e}', 'danger')
        
        cur.close()
        conn.close()
        
    return redirect(url_for('tournament_detail', tournament_id=tournament_id))

# Kullanıcı Girişi
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Girilen şifreyi MD5 ile hashle
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT user_id, username, password FROM Users WHERE username = %s", (username,))
        user = cur.fetchone()
        
        if user and user[2] == hashed_password:  # Hash edilmiş şifrelerle karşılaştırma
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Başarıyla giriş yaptınız!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Geçersiz kullanıcı adı veya şifre!', 'danger')
    
    return render_template('login.html')

# Kullanıcı Çıkış
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Başarıyla çıkış yaptınız.', 'success')
    return redirect(url_for('index'))

# Yeni Kullanıcı Kaydı
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        favorite_game = request.form['favorite_game']
        
        # Şifre doğrulaması - güçlü şifre için regex kontrolü
        # En az 8 karakter, en az 1 büyük harf, 1 küçük harf, 1 sayı ve 1 özel karakter
        password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
        
        if not re.match(password_pattern, password):
            flash('Şifreniz en az 8 karakter uzunluğunda olmalı ve en az 1 büyük harf, 1 küçük harf, 1 sayı ve 1 özel karakter (@$!%*?&) içermelidir.', 'danger')
            return render_template('register.html')
        
        # Şifreyi MD5 ile hashle
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Öncelikle kullanıcı adının benzersiz olup olmadığını kontrol edelim
            cur.execute("SELECT COUNT(*) FROM Users WHERE username = %s", (username,))
            if cur.fetchone()[0] > 0:
                flash('Bu kullanıcı adı zaten kullanımda. Lütfen başka bir kullanıcı adı seçin.', 'danger')
                cur.close()
                conn.close()
                return render_template('register.html')
                
            # E-posta adresinin benzersiz olup olmadığını kontrol edelim
            cur.execute("SELECT COUNT(*) FROM Users WHERE email = %s", (email,))
            if cur.fetchone()[0] > 0:
                flash('Bu e-posta adresi zaten kullanımda. Lütfen başka bir e-posta adresi kullanın.', 'danger')
                cur.close()
                conn.close()
                return render_template('register.html')
                
            # Kontroller başarılıysa yeni kullanıcıyı ekle
            cur.execute(
                "INSERT INTO Users (username, email, password, favorite_game) VALUES (%s, %s, %s, %s)",
                (username, email, hashed_password, favorite_game)
            )
            conn.commit()
            flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
        except psycopg2.Error as e:
            conn.rollback()
            # Genel hata durumları için daha kullanıcı dostu mesaj
            error_message = 'Kayıt sırasında bir hata oluştu. Lütfen bilgilerinizi kontrol edip tekrar deneyin.'
            flash(error_message, 'danger')
        
        cur.close()
        conn.close()
    
    return render_template('register.html')

# Takım Oluşturma
@app.route('/create_team', methods=['GET', 'POST'])
@login_required  # Oturum gerektirir
def create_team():
    if request.method == 'POST':
        team_name = request.form['team_name']
        game_type = request.form['game_type']
        tournament_id = request.form.get('tournament_id')
        user_id = session['user_id']  # Oturumdan kullanıcı id'sini al
        username = session.get('username', 'Bilinmeyen Kullanıcı')
        
        # Oyuncu bilgilerini al
        player2 = request.form.get('player2', '')
        player3 = request.form.get('player3', '')
        player4 = request.form.get('player4', '')
        player5 = request.form.get('player5', '')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Takımı oluştur - kullanıcıyı lider olarak ayarla
            if tournament_id and tournament_id.strip():
                cur.execute(
                    "INSERT INTO Teams (team_name, game_type, leader_id, tournament_id) VALUES (%s, %s, %s, %s) RETURNING team_id",
                    (team_name, game_type, user_id, tournament_id)
                )
            else:
                cur.execute(
                    "INSERT INTO Teams (team_name, game_type, leader_id) VALUES (%s, %s, %s) RETURNING team_id",
                    (team_name, game_type, user_id)
                )
            
            team_id = cur.fetchone()[0]
            
            # Takım üyelerini kaydet (gelecekte kullanım için database'de TeamMembers tablosu oluşturmak gerekebilir)
            team_members = [
                {'name': username, 'role': 'Takım Lideri'},
                {'name': player2, 'role': 'Oyuncu'},
                {'name': player3, 'role': 'Oyuncu'},
                {'name': player4, 'role': 'Oyuncu'},
                {'name': player5, 'role': 'Oyuncu'}
            ]
            
            # Burada TeamMembers tablosu olsaydı buraya eklerdik
            # Şimdilik sadece takımı oluşturuyoruz
            
            conn.commit()
            flash(f'Takım\u0131n\u0131z başar\u0131yla oluşturuldu! Tak\u0131m ID: {team_id}', 'success')
            return redirect(url_for('profile'))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Hata: {e}', 'danger')
        
        cur.close()
        conn.close()
        return redirect(url_for('create_team'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT tournament_id, game_type, 
        COALESCE(tournament_name, 'Turnuva #' || tournament_id || ' - ' || game_type) AS tournament_name 
        FROM Tournaments
        WHERE tournament_date >= CURRENT_DATE  -- Sadece gelecekteki veya bugünkü turnuvaları göster
        ORDER BY tournament_date ASC
    """)
    tournaments = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # session bilgisini template'e gönder
    user_info = {'username': session.get('username', ''), 'user_id': session.get('user_id', '')}
    return render_template('create_team.html', tournaments=tournaments, session=user_info)

# Admin Giriş Sayfası
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Admin girişi başarılı!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Hatalı kullanıcı adı veya şifre!', 'danger')
    
    return render_template('admin_login.html')

# Admin Çıkış
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Başarıyla çıkış yapıldı.', 'success')
    return redirect(url_for('index'))

# Admin Kontrol Paneli
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # İstatistikleri al
    cur.execute("SELECT COUNT(*) FROM Users")
    user_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM Tournaments")
    tournament_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM Teams")
    team_count = cur.fetchone()[0]
    
    cur.execute("SELECT SUM(prize_pool) FROM Tournaments")
    total_prize = cur.fetchone()[0] or 0
    
    # Önce tournament_name sütunu var mı kontrol edelim
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'tournaments' AND column_name = 'tournament_name'
    """)
    
    has_tournament_name = cur.fetchone() is not None
    
    # Eğer tournament_name sütunu yoksa ekleyelim
    if not has_tournament_name:
        cur.execute("ALTER TABLE Tournaments ADD COLUMN tournament_name VARCHAR(100);")
        conn.commit()
        flash('Veritabanı yapısı güncellendi!', 'success')
    
    # Turnuvaları al
    cur.execute("""
        SELECT 
            tournament_id, 
            game_type, 
            tournament_date, 
            prize_pool,
            COALESCE(tournament_name, 'Turnuva #' || tournament_id || ' - ' || game_type) AS tournament_name
        FROM Tournaments 
        ORDER BY tournament_date DESC
    """)
    tournaments = cur.fetchall()
    
    # Son olayları al
    cur.execute("SELECT * FROM Trigger_Logs ORDER BY created_at DESC LIMIT 5")
    recent_logs = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('admin_dashboard.html', 
                           user_count=user_count, 
                           tournament_count=tournament_count,
                           team_count=team_count,
                           total_prize=total_prize,
                           recent_logs=recent_logs,
                           tournaments=tournaments)

# Turnuva Sonuçları Sayfası (Herkese Açık, Yönetim Yok)
@app.route('/results')
def results():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Turnuva sonuçlarını takım ve turnuva isimleriyle birlikte getir
    cur.execute("""
        SELECT 
            tr.result_id, 
            t.tournament_id,
            COALESCE(t.tournament_name, 'Turnuva #' || t.tournament_id || ' - ' || t.game_type) AS tournament_name,
            tm.team_id,
            tm.team_name,
            tr.rank, 
            tr.prize_won,
            t.game_type
        FROM Tournament_Results tr
        JOIN Tournaments t ON tr.tournament_id = t.tournament_id
        JOIN Teams tm ON tr.team_id = tm.team_id
        ORDER BY tr.result_id DESC
    """)
    
    # Sonuçları alıp daha düzenli bir şekilde saklayalım
    result_data = []
    for row in cur.fetchall():
        result = {
            'result_id': row[0],
            'tournament_id': row[1],
            'tournament_name': row[2],
            'team_id': row[3],
            'team_name': row[4],
            'rank': row[5],
            'prize_won': row[6],
            'game_type': row[7]
        }
        result_data.append(result)
    
    cur.close()
    conn.close()
    
    return render_template('results.html', results=result_data)

# Turnuva Sonuçları Yönetimi (Sadece Admin)
@app.route('/admin/results', methods=['GET', 'POST'])
@admin_required
def admin_results():
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        action = request.form['action']
        result_id = request.form.get('result_id')
        prize_won = request.form.get('prize_won')
        
        try:
            if action == 'update' and result_id and prize_won:
                cur.execute(
                    "UPDATE Tournament_Results SET prize_won = %s WHERE result_id = %s",
                    (float(prize_won), int(result_id))
                )
                conn.commit()
                flash('Sonuç güncellendi!', 'success')
            elif action == 'delete' and result_id:
                cur.execute("DELETE FROM Tournament_Results WHERE result_id = %s", (int(result_id),))
                conn.commit()
                flash('Sonuç silindi!', 'success')
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Hata: {e}', 'danger')
    
    # Turnuva ve takım isimlerini de içeren daha detaylı sorgu
    cur.execute("""
        SELECT r.result_id, r.tournament_id, r.team_id, r.rank, r.prize_won,
               t.tournament_name, tm.team_name
        FROM Tournament_Results r
        LEFT JOIN Tournaments t ON r.tournament_id = t.tournament_id
        LEFT JOIN Teams tm ON r.team_id = tm.team_id
        ORDER BY r.tournament_id, r.rank
    """)
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('admin_results.html', results=results)

# En İyi Oyuncular
@app.route('/top_players')
def top_players():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM get_top_players()")
    top_players = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('results.html', top_players=top_players)

# Kullanıcı Profili
@app.route('/profile')
@login_required
def profile():
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Kullanıcı bilgilerini al
    cur.execute("SELECT username, email, favorite_game, profile_update_time FROM Users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    
    # Tüm turnuvaları düzenli olarak göstermek için doğrudan turnuva katılımlarını sorgula
    user_tournaments = []
    from datetime import datetime
    current_date = datetime.now().date()
    
    # Kullanıcının lider olduğu tüm takımları al
    cur.execute("""
        SELECT t.team_id, t.team_name, t.game_type, t.tournament_id
        FROM Teams t
        WHERE t.leader_id = %s
    """, (user_id,))
    teams = cur.fetchall()
    
    # Turnuva ID'si olan tüm takımlar için turnuva bilgilerini al
    for team in teams:
        if team[3] is not None:  # tournament_id varsa
            team_id = team[0]
            team_name = team[1]
            tournament_id = team[3]
            
            # Turnuva hakkında bilgi al
            cur.execute("""
                SELECT t.tournament_date, t.game_type, 
                COALESCE(t.tournament_name, 'Turnuva #' || t.tournament_id || ' - ' || t.game_type) AS tournament_name,
                (SELECT COUNT(*) FROM Tournament_Results tr WHERE tr.tournament_id = t.tournament_id AND tr.team_id = %s) AS has_results
                FROM Tournaments t 
                WHERE t.tournament_id = %s
            """, (team_id, tournament_id))
            
            tournament_info = cur.fetchone()
            
            if tournament_info:
                tournament_date = tournament_info[0]
                game_type = tournament_info[1]
                tournament_name = tournament_info[2]
                has_results = tournament_info[3] > 0
                
                # Turnuva sonuçlarını kontrol et
                if has_results:
                    # Sonuçlanmış turnuva - sonuç bilgilerini al
                    cur.execute("""
                        SELECT rank, prize_won
                        FROM Tournament_Results
                        WHERE tournament_id = %s AND team_id = %s
                    """, (tournament_id, team_id))
                    result_info = cur.fetchone()
                    rank = result_info[0] if result_info else '-'
                    prize = result_info[1] if result_info else 0
                else:
                    # Devam eden turnuva
                    rank = 'Devam Ediyor'
                    prize = 0
                
                user_tournaments.append((tournament_id, game_type, tournament_date, rank, prize, tournament_name))
    
    # Başarılar kartı için gerekli değişkenler
    first_places = 0
    user_favorite_game = user[2] if user and user[2] else None
    
    # Birinci olan turnuvaları say
    for tournament in user_tournaments:
        if tournament[3] == 1:  # rank = 1 (birincilik)
            first_places += 1
    
    cur.close()
    conn.close()
    
    if user:
        profile_update_time = user[3] if user[3] else 'Henüz güncelleme yapılmadı'
        return render_template('profile.html', 
                               user=user, 
                               tournaments=user_tournaments, 
                               profile_update_time=profile_update_time,
                               first_places=first_places,
                               user_favorite_game=user_favorite_game)
    else:
        flash('Kullanıcı bulunamadı!', 'danger')
        return redirect(url_for('index'))

# Profil Düzenleme
@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    from datetime import datetime
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Mevcut kullanıcı bilgilerini al
    cur.execute("SELECT username, email, favorite_game FROM Users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        favorite_game = request.form['favorite_game']
        password = request.form.get('password')  # Yeni şifre
        password_confirm = request.form.get('password_confirm')  # Şifre tekrarı
        
        # Kullanıcı adı benzersizliğini kontrol et (eğer değiştiyse)
        if username != user[0]:
            cur.execute("SELECT COUNT(*) FROM Users WHERE username = %s AND user_id != %s", (username, user_id))
            if cur.fetchone()[0] > 0:
                flash('Bu kullanıcı adı zaten kullanılıyor!', 'danger')
                cur.close()
                conn.close()
                return redirect(url_for('edit_profile'))
        
        # Şifre kontrolü
        if password and password.strip():
            if not password_confirm or password != password_confirm:
                flash('Şifreler eşleşmiyor!', 'danger')
                cur.close()
                conn.close()
                return redirect(url_for('edit_profile'))
        
        try:
            now = datetime.now()
            update_time = now.strftime("%d.%m.%Y %H:%M")
            
            # Şifre değiştirildi mi?
            if password and password.strip():
                cur.execute(
                    "UPDATE Users SET username = %s, email = %s, favorite_game = %s, password = %s, profile_update_time = %s WHERE user_id = %s",
                    (username, email, favorite_game, password, update_time, user_id)
                )
            else:
                cur.execute(
                    "UPDATE Users SET username = %s, email = %s, favorite_game = %s, profile_update_time = %s WHERE user_id = %s",
                    (username, email, favorite_game, update_time, user_id)
                )
                
            conn.commit()
            flash('Profil bilgileriniz başarıyla güncellendi!', 'success')
            return redirect(url_for('profile'))
            
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Hata: {e}', 'danger')
    
    # Oyun seçeneklerini al
    game_options = ['Valorant', 'League of Legends', 'CS:GO']
    
    cur.close()
    conn.close()
    
    return render_template('edit_profile.html', user=user, game_options=game_options)

# Diğer kullanıcının profilini görüntüleme
@app.route('/player/<int:user_id>')
def player_profile(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Kullanıcı bilgilerini al
    cur.execute("SELECT username, email, favorite_game FROM Users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    
    # Kullanıcının katıldığı turnuvaları al (get_user_tournaments fonksiyonu kullanılarak)
    cur.execute("SELECT * FROM get_user_tournaments(%s)", (user_id,))
    tournaments = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if user:
        return render_template('player_profile.html', user=user, tournaments=tournaments)
    else:
        flash('Kullanıcı bulunamadı!', 'danger')
        return redirect(url_for('index'))

# Turnuva Düzenleme Sayfası
@app.route('/admin/edit_tournament/<int:tournament_id>', methods=['GET', 'POST'])
@admin_required
def edit_tournament(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Turnuvayı getir
    cur.execute("SELECT * FROM Tournaments WHERE tournament_id = %s", (tournament_id,))
    tournament = cur.fetchone()
    
    if not tournament:
        flash('Turnuva bulunamadı!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        game_type = request.form['game_type']
        tournament_date = request.form['tournament_date']
        prize_pool = request.form['prize_pool']
        tournament_name = request.form['tournament_name']
        
        try:
            # Önce tournament_name sütunu var mı kontrol edelim
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'tournaments' AND column_name = 'tournament_name'
            """)
            
            has_tournament_name = cur.fetchone() is not None
            
            # Eğer tournament_name sütunu yoksa ekleyelim
            if not has_tournament_name:
                cur.execute("ALTER TABLE Tournaments ADD COLUMN tournament_name VARCHAR(100);")
                flash('Veritabanı yapısı güncellendi!', 'success')
            
            # Turnuvayı güncelle
            if has_tournament_name:
                cur.execute("""
                    UPDATE Tournaments 
                    SET game_type = %s, tournament_date = %s, prize_pool = %s, tournament_name = %s 
                    WHERE tournament_id = %s
                """, (game_type, tournament_date, prize_pool, tournament_name, tournament_id))
            else:
                cur.execute("""
                    UPDATE Tournaments 
                    SET game_type = %s, tournament_date = %s, prize_pool = %s 
                    WHERE tournament_id = %s
                """, (game_type, tournament_date, prize_pool, tournament_id))
                
                # Yeni eklenen sütun için güncelleme
                cur.execute("""
                    UPDATE Tournaments 
                    SET tournament_name = %s
                    WHERE tournament_id = %s
                """, (tournament_name, tournament_id))
            
            conn.commit()
            flash('Turnuva başarıyla güncellendi!', 'success')
            return redirect(url_for('admin_dashboard'))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Hata: {e}', 'danger')
    
    cur.close()
    conn.close()
    
    return render_template('admin_edit_tournament.html', tournament=tournament)

# Turnuva Silme İşlemi
@app.route('/admin/delete_tournament/<int:tournament_id>', methods=['POST'])
@admin_required
def delete_tournament(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # İlişkili kayıtları kontrol et
        cur.execute("SELECT COUNT(*) FROM Teams WHERE tournament_id = %s", (tournament_id,))
        team_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM Tournament_Results WHERE tournament_id = %s", (tournament_id,))
        result_count = cur.fetchone()[0]
        
        if team_count > 0 or result_count > 0:
            flash('Bu turnuva silinemez çünkü bağlı takımlar veya sonuçlar var!', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        # Turnuvayı sil
        cur.execute("DELETE FROM Tournaments WHERE tournament_id = %s", (tournament_id,))
        conn.commit()
        flash('Turnuva başarıyla silindi!', 'success')
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Hata: {e}', 'danger')
    
    cur.close()
    conn.close()
    
    return redirect(url_for('admin_dashboard'))

# Yeni Turnuva Ekleme
@app.route('/admin/add_tournament', methods=['GET', 'POST'])
@admin_required
def add_tournament():
    if request.method == 'POST':
        game_type = request.form['game_type']
        tournament_date = request.form['tournament_date']
        prize_pool = request.form['prize_pool']
        
        # Önce tournament_name sütunu var mı kontrol edelim
        conn = get_db_connection()
        conn.autocommit = True  # Otomatik commit işlemi için
        cur = conn.cursor()
        
        try:
            # Sütun var mı kontrol et
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'tournaments' AND column_name = 'tournament_name'
            """)
            
            has_tournament_name = cur.fetchone() is not None
            
            # Turnuva adını formdan alalım
            tournament_name = request.form['tournament_name']
            
            # Eğer tournament_name sütunu yoksa ekleyelim
            if not has_tournament_name:
                cur.execute("ALTER TABLE Tournaments ADD COLUMN tournament_name VARCHAR(100);")
                flash('Veritabanı yapısı güncellendi!', 'success')
            
            # Turnuvayı ekle
            if has_tournament_name:
                cur.execute("""
                    INSERT INTO Tournaments (game_type, tournament_date, prize_pool, tournament_name)
                    VALUES (%s, %s, %s, %s)
                """, (game_type, tournament_date, prize_pool, tournament_name))
            else:
                cur.execute("""
                    INSERT INTO Tournaments (game_type, tournament_date, prize_pool)
                    VALUES (%s, %s, %s)
                """, (game_type, tournament_date, prize_pool))
                
                # Son eklenen turnuvanın ID'sini alıp adını güncelleyelim
                cur.execute("SELECT lastval()")
                last_id = cur.fetchone()[0]
                
                cur.execute("""
                    UPDATE Tournaments 
                    SET tournament_name = %s
                    WHERE tournament_id = %s
                """, (tournament_name, last_id))
            
            conn.commit()
            flash('Yeni turnuva başarıyla eklendi!', 'success')
            return redirect(url_for('admin_dashboard'))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Hata: {e}', 'danger')
        finally:
            cur.close()
            conn.close()
    
    return render_template('admin_add_tournament.html')

# Kullanıcı Yönetim Sayfası
@app.route('/admin/users')
@admin_required
def admin_users():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Temiz bir veri yapısı oluşturacağız
    cur.execute("SELECT user_id, username, email, password, favorite_game, created_at FROM Users ORDER BY created_at DESC")
    users_raw = cur.fetchall()
    
    # Verileri düzenli hale getiriyoruz
    users = []
    for user in users_raw:
        user_dict = {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'password': user[3],
            'favorite_game': user[4] if user[4] and isinstance(user[4], str) else ('Belirtilmemiş' if user[4] is None else str(user[4])),
            'created_at': user[5].strftime('%d.%m.%Y') if user[5] and hasattr(user[5], 'strftime') else ('Belirtilmemiş' if user[5] is None else str(user[5]))
        }
        users.append(user_dict)
    
    cur.close()
    conn.close()
    
    return render_template('admin_users.html', users=users)

# Kullanıcı Düzenleme Sayfası
@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Kullanıcıyı getir
    cur.execute("SELECT * FROM Users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    
    if not user:
        flash('Kullanıcı bulunamadı!', 'danger')
        return redirect(url_for('admin_users'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        favorite_game = request.form['favorite_game']
        
        try:
            cur.execute("""
                UPDATE Users 
                SET username = %s, email = %s, favorite_game = %s 
                WHERE user_id = %s
            """, (username, email, favorite_game, user_id))
            
            conn.commit()
            flash('Kullanıcı başarıyla güncellendi!', 'success')
            return redirect(url_for('admin_users'))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Hata: {e}', 'danger')
    
    cur.close()
    conn.close()
    
    return render_template('admin_edit_user.html', user=user)

# Kullanıcı Silme İşlemi
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # İlişkili kayıtları kontrol et
        cur.execute("SELECT COUNT(*) FROM Teams WHERE leader_id = %s", (user_id,))
        team_count = cur.fetchone()[0]
        
        if team_count > 0:
            flash('Bu kullanıcı silinemez çünkü lider olduğu takımlar var!', 'danger')
            return redirect(url_for('admin_users'))
        
        # Kullanıcıyı sil
        cur.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
        conn.commit()
        flash('Kullanıcı başarıyla silindi!', 'success')
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Hata: {e}', 'danger')
    
    cur.close()
    conn.close()
    
    return redirect(url_for('admin_users'))

# Takım Yönetimi Sayfası
@app.route('/admin/teams')
@admin_required
def admin_teams():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Tüm takımları getir
    cur.execute("""
        SELECT t.*, u.username, tr.game_type as tournament_game, 
        tr.tournament_name as tournament_name
        FROM Teams t 
        LEFT JOIN Users u ON t.leader_id = u.user_id
        LEFT JOIN Tournaments tr ON t.tournament_id = tr.tournament_id 
        ORDER BY t.created_at DESC
    """)
    teams_raw = cur.fetchall()
    
    # Tarih formatını düzenle
    teams = []
    for team in teams_raw:
        team_list = list(team)
        # date formatını düzenle
        if team[4] and not isinstance(team[4], str):
            team_list[4] = team[4].strftime('%d.%m.%Y')
        teams.append(team_list)
    
    cur.close()
    conn.close()
    
    return render_template('admin_teams.html', teams=teams)

# Takım Düzenleme Sayfası
@app.route('/admin/edit_team/<int:team_id>', methods=['GET', 'POST'])
@admin_required
def edit_team(team_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Takımı getir
    cur.execute("SELECT * FROM Teams WHERE team_id = %s", (team_id,))
    team = cur.fetchone()
    
    if not team:
        flash('Takım bulunamadı!', 'danger')
        return redirect(url_for('admin_teams'))
    
    # Kullanıcıları getir (takım lideri seçenekleri için)
    cur.execute("SELECT user_id, username FROM Users ORDER BY username")
    users = cur.fetchall()
    
    # Turnuvaları getir
    cur.execute("SELECT tournament_id, tournament_name, game_type FROM Tournaments ORDER BY tournament_date DESC")
    tournaments = cur.fetchall()
    
    if request.method == 'POST':
        team_name = request.form['team_name']
        leader_id = request.form['leader_id']
        tournament_id = request.form.get('tournament_id', None)
        game_type = request.form['game_type']
        
        if tournament_id == '':
            tournament_id = None
        
        try:
            cur.execute("""
                UPDATE Teams 
                SET team_name = %s, leader_id = %s, tournament_id = %s, game_type = %s 
                WHERE team_id = %s
            """, (team_name, leader_id, tournament_id, game_type, team_id))
            
            conn.commit()
            flash('Takım başarıyla güncellendi!', 'success')
            return redirect(url_for('admin_teams'))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Hata: {e}', 'danger')
    
    cur.close()
    conn.close()
    
    return render_template('admin_edit_team.html', team=team, users=users, tournaments=tournaments)

# Takım Silme İşlemi
@app.route('/admin/delete_team/<int:team_id>', methods=['POST'])
@admin_required
def delete_team(team_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # İlişkili kayıtları kontrol et
        cur.execute("SELECT COUNT(*) FROM Tournament_Results WHERE team_id = %s", (team_id,))
        result_count = cur.fetchone()[0]
        
        if result_count > 0:
            flash('Bu takım silinemez çünkü turnuva sonuçları var!', 'danger')
            return redirect(url_for('admin_teams'))
        
        # Takımı sil
        cur.execute("DELETE FROM Teams WHERE team_id = %s", (team_id,))
        conn.commit()
        flash('Takım başarıyla silindi!', 'success')
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Hata: {e}', 'danger')
    
    cur.close()
    conn.close()
    
    return redirect(url_for('admin_teams'))

# Turnuvadan Çekilme
@app.route('/tournament/<int:tournament_id>/leave', methods=['POST'])
@login_required
def leave_tournament(tournament_id):
    user_id = session['user_id']
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Kullanıcının lider olduğu ve bu turnuvaya kayıtlı takımları bulalım
    cur.execute("""
        SELECT team_id, team_name FROM Teams 
        WHERE leader_id = %s AND tournament_id = %s
    """, (user_id, tournament_id))
    
    team = cur.fetchone()
    if not team:
        flash('Bu turnuvaya kayıtlı takımınız bulunamadı!', 'danger')
        return redirect(url_for('profile'))
    
    team_id = team[0]
    team_name = team[1]
    
    try:
        # Turnuva sonucu var mı kontrol edelim
        cur.execute("SELECT COUNT(*) FROM Tournament_Results WHERE team_id = %s AND tournament_id = %s", (team_id, tournament_id))
        has_results = cur.fetchone()[0] > 0
        
        if has_results:
            flash('Sonuçlanmış bir turnuvadan çekilemezsiniz!', 'danger')
        else:
            # Takımın turnuva kaydını kaldıralım
            cur.execute("UPDATE Teams SET tournament_id = NULL WHERE team_id = %s", (team_id,))
            conn.commit()
            flash(f'{team_name} takımı turnuvadan başarıyla çekildi!', 'success')
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Hata: {e}', 'danger')
    
    cur.close()
    conn.close()
    
    return redirect(url_for('profile'))

if __name__ == '__main__':
    app.run(debug=True , port=5002)