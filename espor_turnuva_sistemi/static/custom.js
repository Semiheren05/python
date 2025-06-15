/**
 * E-Spor Arena - Custom JavaScript
 * 
 * Bu dosya dinamik UI bileşenlerini yönetir
 */

// Progress bar'ları ayarla
function setupProgressBars() {
    const progressBars = document.querySelectorAll('.progress-bar[data-percent]');
    progressBars.forEach(bar => {
        const percent = bar.getAttribute('data-percent');
        bar.style.width = `${percent}%`;
        bar.setAttribute('aria-valuenow', percent);
    });
}

// Sayfa yüklendiğinde tüm gerekli fonksiyonları çalıştır
document.addEventListener('DOMContentLoaded', function() {
    setupProgressBars();
});
