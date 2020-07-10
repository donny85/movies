# movies

- Reorganize your movies library on the hard drive.
- Download movies metadata from csfd.cz.
- Create new directory views with files (hardlinks) groupped by selected attributes.

## Example of use:

### Prepare

Create a virtualenv, install `requirements.txt` using `pip` and/or _activate_ the venv.
Current Working Directory is this project root.

```shell script
mkvirtualenv -a . -r "requirements.txt" movies
```
### Get the metadata

Select a source directory containing the media files, e.g. `./media/` and choose a path to
the output CSV file, let's call it `./movies_metadata.csv`

When looking for the metadata, let's ignore some words that are obviously not part
of a movie name. There are some in `assets/stopwords.txt`, you can provide 
an additional list by specifying its file name in the `-s` argument.

We take a list of files, and run it through the `movies_metadata.py`, that will
look for movie records on čsfd.cz and print results to a csv table.

The input - `/bin/ls -Q1 "./media/"` - is our fake csv table with only first 
column (filename) filled. We can expect each file name to be unique.

```shell script
/bin/ls -Q1 "./media/" | ./movies_metadata.py -o "./movies_metadata.csv"
```

The default settings can be overriden using few command-line arguments.
See `movies_metadata.py --help` for more information.

### Manual selection

The result CSV might contain more results for each file. You have to open the file
in Excel, Calc or whatever, and remove the incorrect lines one by one.

In the following step you'll need a CSV file with unique file names in first column,
or in another words, a file with exactly one line per a media file.

### Create new directory tree with hardlinks

Keep your source movies directory untouched, even after creating the
new directory tree.

The target directory must be on the same filesystem (e.g. `./library/`)
and the file system must support hardlinks (no FAT or exFAT, but NTFS or EXT4 is fine).

```shell script
./movies_tree.sh -i "./movies_metadata.csv" -d "./media/" -o "./library/"
```

Now the `./library/` should contain new directory tree with movies grouped by
selected attributes.
