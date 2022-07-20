const fs = require('fs')

const threshold = 0
const errorModel = './experiments/besu/error_models.json'
const dest = './experiments/besu/error_models_processed_<idx>.json'

const aggro = [
    {
        amplification: 1.025,
        number: 5
    }, {
        amplification: 1.05,
        number: 5
    }, {
        amplification: 1.1,
        number: 100
    }
]

const main = () => {
    //read error models
    const file = fs.readFileSync(errorModel)
    const errormodels = JSON.parse(file).experiments

    aggro.forEach((agg, i) => {
        const processed = errormodels
            .filter(model => model.original_mean_rate > threshold && model.original_mean_rate < 1)
            .sort((a, b) => b.original_mean_rate - a.original_mean_rate)
            .map(obj => {
                return {
                    syscall_name: obj.syscall_name,
                    error_code: obj.error_code,
                    original_mean_rate: obj.original_mean_rate,
                    failure_rate: obj.original_mean_rate * agg.amplification
                }
            })
            .slice(0, agg.number)

        const obj = {
            experiments: processed
        }
        fs.writeFileSync(dest.replace('<idx>', `${i + 1}`), JSON.stringify(obj, null, 2))
    })
}

main()